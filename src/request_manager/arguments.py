import argparse
import os
from dataclasses import dataclass
from functools import partial
from types import UnionType
from typing import Callable, ClassVar, Sequence, Union, get_args, get_origin

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined


def build_name(
    env_name: str,
    env_separator: str,
    name: str | Sequence[str],
) -> str:
    if isinstance(name, str):
        name = [name]
    return f"{env_name}{env_separator}{env_separator.join(name)}"


@dataclass(frozen=True, slots=True)
class DefaultArguments:
    @dataclass(frozen=True, slots=True)
    class Environment:
        NAME: ClassVar[str] = "RM"
        SEP: ClassVar[str] = "__"
        PREFIX: ClassVar[str] = f"{NAME}{SEP}"

        build: Callable[[str], str] = staticmethod(partial(build_name, NAME, SEP))

    env: ClassVar[Environment] = Environment()

    @classmethod
    def get(cls, name: str) -> str | None:
        return os.environ.get(cls.env.build(name), None)


def add_arguments_from_model(
    parser: argparse.ArgumentParser,
    model: type[BaseModel],
    env: type[DefaultArguments] = DefaultArguments,
) -> None:
    def unwrap_optional(annotation: type | None) -> tuple[type, bool]:
        if annotation is None:
            raise TypeError(
                "Field has no resolvable annotation; cannot build CLI argument"
            )

        origin = get_origin(annotation)
        if origin is Union or origin is UnionType:
            args = [a for a in get_args(annotation) if a is not type(None)]
            if len(args) == 1:
                return args[0], True
        return annotation, False

    def flag_for(field_name: str) -> str:
        return f"--{field_name.replace('_', '-')}"

    def short_flag(field: FieldInfo) -> str | None:
        extra = field.json_schema_extra
        if not isinstance(extra, dict):
            return None

        if "short" not in extra:
            return None

        value = extra["short"]  # type: ignore
        return value if isinstance(value, str) else None

    for name, field in model.model_fields.items():
        annotation, is_optional = unwrap_optional(field.annotation)

        env_default = env.get(name.upper())
        has_pydantic_default = field.default is not PydanticUndefined
        pydantic_default = field.default if has_pydantic_default else None

        default = env_default if env_default is not None else pydantic_default
        required = default is None and not is_optional and not has_pydantic_default

        short = short_flag(field)
        flags = [short, flag_for(name)] if short else [flag_for(name)]

        help_text = field.description or name
        help_text += f"(Env. {env.env.build(name.upper())})"

        if annotation is bool:
            parser.add_argument(
                *flags,
                dest=name,
                default=bool(default),
                action="store_true" if not default else "store_false",
                help=help_text,
            )
        else:
            parser.add_argument(
                *flags,
                dest=name,
                default=default,
                type=annotation,
                required=required,
                help=help_text,
            )


def load_arguments[T: BaseModel](type_: type[T]) -> T:
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="request-manager",
        description="Test different API endpoints, capturing results and forwarding them",
    )

    add_arguments_from_model(parser, type_)

    return type_.model_validate(vars(parser.parse_args()))
