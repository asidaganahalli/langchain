from libcst.codemod import CodemodTest

from langchain_cli.namespaces.migrate.codemods.replace_imports import (
    ReplaceImportsCodemod,
)


class TestReplaceImportsCommand(CodemodTest):
    TRANSFORM = ReplaceImportsCodemod

    def test_single_import(self) -> None:
        before = """
        from langchain.chat_models import ChatOpenAI
        """
        after = """
        from langchain_openai import ChatOpenAI
        """
        self.assertCodemod(before, after)

    def test_noop_import(self) -> None:
        code = """
        from foo  import ChatOpenAI
        """
        self.assertCodemod(code, code)

    def test_mixed_imports(self) -> None:
        before = """
        from langchain.chat_models import ChatOpenAI, ChatAnthropic
        """
        after = """
        from langchain.chat_models import ChatAnthropic
        from langchain_openai import ChatOpenAI
        """
        self.assertCodemod(before, after)
