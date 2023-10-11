from llmagic.tokenizer import tokenizer
from rich.panel import Panel
from rich.console import Group
from rich.style import Style
from rich.text import Text
from abc import ABC, abstractmethod

from llmagic.types import TruncationStrategy
from llmagic.truncation import truncate


class AbstractBlock(ABC):
    @abstractmethod
    def full_tokens(self) -> list[int]:
        pass

    @abstractmethod
    def full_text(self) -> str:
        pass

    @abstractmethod
    def tokens(self) -> list[int]:
        pass

    @abstractmethod
    def rich_text(self, max_tokens: int | None = None) -> Panel:
        pass

    @abstractmethod
    def text(self) -> str:
        pass

    def full_size(self):
        return len(self.full_tokens())

    def size(self):
        return len(self.tokens())
    def add_ellipses(self, text:str, max_value:int|None) -> str:
        pass

class Block(AbstractBlock):
    def __init__(
        self,
        children: list[AbstractBlock] | None = None,
        text: str | None = None,
        name: str | None = None,
        max_tokens: int | None = None,
        truncate: TruncationStrategy = "right",
        separator: str = "",
    ):
        self.name = name
        self.max_tokens = max_tokens
        self.truncation_strategy: TruncationStrategy = truncate
        self.children = children if children is not None else []

        # TODO: make tokenizer configurable
        self.separator = separator

        if text is not None:
            prepend = [TextBlock(text=text)]
            if self.separator:
                prepend.append(TextBlock(text=self.separator, name="separator"))
            self.children = prepend + self.children

        if self.max_tokens is None:
            pass
        elif self.max_tokens < 0:
            raise ValueError(
                f"max_tokens should be a positive integer and not {self.max_tokens}"
            )

    def full_tokens(self) -> list[int]:
        joined_tokens: list[int] = []
        for _, child in enumerate(self.children):
            joined_tokens += child.full_tokens()
        return joined_tokens

    def full_text(self) -> str:
        return tokenizer.decode(self.full_tokens())

    def tokens(self) -> list[int]:
        joined_tokens: list[int] = []
        for _, child in enumerate(self.children):
            joined_tokens += child.tokens()

        return truncate(
            joined_tokens,
            max_tokens=self.max_tokens,
            truncation_strategy=self.truncation_strategy,
        )["tokens"]

    
        

    def rich_text(
        self,
        max_tokens: int | None = None,
        truncation_strategy: TruncationStrategy | None = None,
    ) -> Panel:
        if max_tokens is None:
            max_tokens = self.max_tokens
        if truncation_strategy is None:
            truncation_strategy = self.truncation_strategy

        rich_texts = []
        tokens_seen = 0

        for child in self.children:
            if not max_tokens or (tokens_seen + len(child.tokens())) < max_tokens:
                # We can add this child and have tokens left over
                rich_texts.append(child.rich_text())
                tokens_seen += len(child.tokens())
            else:
                # We exceed the max tokens amount
                number_allowed = max(max_tokens - tokens_seen, 0)
                rich_texts.append(
                    child.rich_text(
                        max_tokens=number_allowed,
                        truncation_strategy=truncation_strategy,
                    )
                )
                tokens_seen += number_allowed
        return Panel(
            Group(*rich_texts),
            title=self.name or "",
            title_align="left",
            border_style=f"bold blue",
        )

    def text(self) -> str:
        return tokenizer.decode(self.tokens())

    def __repr__(self):
        return f'<Block name="{self.name}" size=[{self.full_size()}/{self.max_tokens or "inf"}] text="{self.text()[:25] + "..."}">'

    def append(self, other: AbstractBlock | str):
        self.__add__(other)

    def __add__(self, other: AbstractBlock | str):
        if isinstance(other, str):
            if self.separator and self.children:
                self.children.append(TextBlock(text=self.separator, name="separator"))
            self.children.append(TextBlock(text=other))
            return self
        elif isinstance(other, AbstractBlock):
            if self.separator and self.children:
                self.children.append(TextBlock(text=self.separator, name="separator"))
            self.children.append(other)
            return self
        else:
            raise TypeError(f"Cannot add type {type(other)} to Block")

    def __len__(self):
        return len(self.full_text())

    def by_name(self):
        pass

    def by_class(self):
        pass

    def __del__(self):
        pass


class SectionBlock(Block):
    def __init__(
        self,
        header: str,
        children: list[AbstractBlock] | None = None,
        text: str | None = None,
        name: str | None = None,
        max_tokens: int | None = None,
        truncate: TruncationStrategy = "right",
        separator: str = "",
    ):
        if children is None:
            children = []

        if text is not None:
            children = [TextBlock(text=text)] + children

        if header is not None:
            if not header.endswith("\n"):
                header = header + "\n"
            children = [TextBlock(text=header, name="header")] + children

        super().__init__(
            children=children,
            text=None,
            name=name,
            max_tokens=max_tokens,
            truncate=truncate,
            separator=separator,
        )


class QueueBlock(Block):
    def __init__(self, queue_size: int = 32, **kwargs):
        super().__init__(**kwargs)
        self.queue_size = queue_size
        self.children = self.children[-queue_size:]

    def add(self, other: AbstractBlock | str):
        if len(self.children) >= self.queue_size:
            self.children.pop(0)
        self.__add__(other)


class TextBlock(AbstractBlock):
    def __init__(
        self,
        text: str,
        max_value: int|None = 3,
        name: str | None = None,
        max_tokens: int | None = None,
        truncate: TruncationStrategy = "right",
    ):
        self._text = text
        self._tokens = tokenizer.encode(text)
        self.name = name
        self.max_tokens = max_tokens
        self.truncation_strategy: TruncationStrategy = truncate
        self.max_value = max_value

    def add_ellipses(self, text:str, max_value:int|None) -> str:
        if max_value is None:
            max_value = self.max_value
        elif len(text) > max_value:
            return text[:max_value-3]+"..."
        else:
            return text

    def rich_text(
        self,
        max_tokens: int | None = None,
        truncation_strategy: TruncationStrategy | None = None,
    ) -> Panel:
        if max_tokens is None:
            max_tokens = self.max_tokens
        if truncation_strategy is None:
            truncation_strategy = self.truncation_strategy

        child_truncated_tokens = truncate(
            self.full_tokens(),
            max_tokens=self.max_tokens,
            truncation_strategy=self.truncation_strategy,
        )
        parent_truncated_tokens = truncate(
            child_truncated_tokens["tokens"],
            max_tokens=max_tokens,
            truncation_strategy=truncation_strategy,
        )

        left_text = tokenizer.decode(
            child_truncated_tokens["remainder_left"]
            + parent_truncated_tokens["remainder_left"]
        )
        right_text = tokenizer.decode(
            parent_truncated_tokens["remainder_right"]
            + child_truncated_tokens["remainder_right"]
        )
        inner_text = tokenizer.decode(parent_truncated_tokens["tokens"])


        display_text = Text()
        display_text.append(left_text, style="bold magenta")
        display_text.append(inner_text, style="bold blue")
        display_text.append(self.add_ellipses(right_text, self.max_value), style="bold magenta")

        return Panel(
            display_text,
            title=self.name or "",
            title_align="left",
            border_style="bold green",
        )

    def full_text(self) -> str:
        return self._text

    def full_tokens(self) -> list[int]:
        return self._tokens

    def text(self) -> str:
        return tokenizer.decode(self.tokens())

    def tokens(self):
        truncated = truncate(
            self.full_tokens(),
            max_tokens=self.max_tokens,
            truncation_strategy=self.truncation_strategy,
        )
        return truncated["tokens"]

    def __repr__(self):
        return f'<Block name="{self.name}" size=[{self.full_size()}/{self.max_tokens or "inf"}] text="{self.text()[:25] + "..."}">'
