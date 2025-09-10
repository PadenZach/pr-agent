from typing import Protocol
from functools import partial

from pr_agent.algo.ai_handlers.base_ai_handler import BaseAiHandler
from pr_agent.algo.ai_handlers.litellm_ai_handler import LiteLLMAIHandler
from pr_agent.algo.pr_processing import get_pr_diff, retry_with_fallback_models
from pr_agent.algo.token_handler import TokenHandler
from pr_agent.config_loader import get_settings
from pr_agent.git_providers import get_git_provider
from pr_agent.git_providers.git_provider import get_main_pr_language
from pr_agent.log import get_logger


def get_docs_for_language(language, style):
    language = language.lower()
    if language == 'java':
        return "Javadocs"
    elif language in ['python', 'lisp', 'clojure']:
        return f"Docstring ({style})"
    elif language in ['javascript', 'typescript']:
        return "JSdocs"
    elif language == 'c++':
        return "Doxygen"
    else:
        return "Docs"

class AITool(Protocol):
    """ Protocol/Base class to inherit from to create new Tools that can be
    added to the AI.
    """
    def __init__(self, pr_url: str, cli_mode=False, args: list = None,
                 ai_handler: partial[BaseAiHandler,] = LiteLLMAIHandler):

        self.git_provider = get_git_provider()(pr_url)
        self.main_language = get_main_pr_language(
            self.git_provider.get_languages(), self.git_provider.get_files()
        )

        self.ai_handler = ai_handler()
        self.ai_handler.main_pr_language = self.main_language

        self.patches_diff = None
        self.prediction = None
        self.cli_mode = cli_mode
        self.vars = {
            "title": self.git_provider.pr.title,
            "branch": self.git_provider.get_pr_branch(),
            "description": self.git_provider.get_pr_description(),
            "language": self.main_language,
            "diff": "",  # empty diff for initial calculation
            "extra_instructions": get_settings().pr_add_docs.extra_instructions,
            "commit_messages_str": self.git_provider.get_commit_messages(),
            'docs_for_language': get_docs_for_language(self.main_language,
                                                       get_settings().pr_add_docs.docs_style),
        }
        self.token_handler = TokenHandler(self.git_provider.pr,
                                          self.vars,
                                          get_settings().pr_add_docs_prompt.system,
                                          get_settings().pr_add_docs_prompt.user)
    
    async def _prepare_prediction(self, model: str):
        get_logger().info('Getting PR diff...')

        self.patches_diff = get_pr_diff(self.git_provider,
                                        self.token_handler,
                                        model,
                                        add_line_numbers_to_hunks=True,
                                        disable_extra_lines=False)

        get_logger().info('Getting AI prediction...')
        self.prediction = await self._get_prediction(model)


    async def run(self):
        try:
            get_logger().info('Generating code Docs for PR...')
            if get_settings().config.publish_output:
                self.git_provider.publish_comment("Generating Documentation...", is_temporary=True)

            get_logger().info('Preparing PR documentation...')
            await retry_with_fallback_models(self._prepare_prediction)
            raise NotImplementedError("Run Protocol unimplemented")
        except Exception as e:
            raise e
        