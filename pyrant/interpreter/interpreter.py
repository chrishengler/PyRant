from pyrant.parser.compiler import Compiler
from .function_dict import function_definitions
from .block_attributes import BlockAttributeManager, BlockAttributes
from pyrant.rant_exceptions import RantInterpreterException
from .synchronizer import Synchronizer, SynchronizerManager
from pyrant.interpreter.formatter import Formatter
from pyrant.lookup.lookup import LookupManager, LookupDictionary
from pyrant.parser.compiler_objects import *
from .regex_state import RegexState

from functools import singledispatch
from random import randrange, randint
from re import sub, Match

compiler = Compiler()


def interpret_external(sentence: str) -> str:
    SynchronizerManager.clear()
    BlockAttributeManager.clear()
    LookupManager.clear_labels()
    return interpret_internal(compiler.compile(sentence))


def interpret_internal(parse_result: RootObject) -> Formatter:
    formatter = Formatter()
    for obj in parse_result:
        resulting_formatter = run(obj)
        if resulting_formatter:
            formatter += resulting_formatter
    return formatter.resolve()


# noinspection PyUnusedLocal
@singledispatch
def run(arg) -> Formatter:
    formatter = Formatter()
    return formatter


@run.register(RootObject)
def _(root: RootObject):
    formatter = Formatter()
    for item in root.contents:
        item_result = run(item)
        if item_result:
            formatter += item_result
    return formatter


@run.register(BlockObject)
def _(block: BlockObject):
    formatter = Formatter()
    attributes: BlockAttributes = BlockAttributeManager.get_attributes()
    first_repetition = True
    synchronizer: Synchronizer | None = None
    if attributes.synchronizer is not None:
        if SynchronizerManager.synchronizer_exists(attributes.synchronizer):
            synchronizer = SynchronizerManager.get_synchronizer(
                attributes.synchronizer)
        else:
            if attributes.synchronizer_type is None:
                raise RantInterpreterException(
                    f"[Interpreter.run](RantBlockObject) tried to define new synchronizer without defining synchronizer type")
            synchronizer = SynchronizerManager.create_synchronizer(
                attributes.synchronizer, attributes.synchronizer_type, len(block.choices))

    while attributes.repetitions:
        if synchronizer is None:
            choice = randrange(0, len(block.choices))
        else:
            choice = synchronizer.next()
            if choice >= len(block.choices):
                raise RantInterpreterException(
                    f"[Interpreter.run](RantBlockObject) tried to get item no. {choice} of {len(block.choices)} - when using synchronizers, make sure you have the same number of choices each time")
        if first_repetition:
            first_repetition = False
            formatter.append(attributes.first)
        elif attributes.repetitions == 1:
            formatter.append(attributes.last)
        attributes.repetitions = attributes.repetitions - 1
        partial_result = run(
            block.choices[choice])
        formatter += partial_result
        if attributes.repetitions:
            formatter.append(attributes.separator)
    return formatter


@run.register(FunctionObject)
def _(func: FunctionObject):
    formatter = Formatter()
    evaluated_args = list()
    for arg in func.args:
        evaluated_args.append(run(arg).resolve())
    if func.func in function_definitions:
        formatter.append(function_definitions[func.func](evaluated_args))
    else:
        raise RantInterpreterException(
            f"[Interpreter::run] no function found named '{func.func}'")
    return formatter


@run.register(TextObject)
def _(text: TextObject):
    formatter = Formatter()
    formatter.append(text.text)
    return formatter


@run.register(LookupObject)
def _(lookup: LookupObject):
    formatter = Formatter()
    dictionary: LookupDictionary = LookupManager[lookup.dictionary]
    formatter.append(dictionary.get(lookup))


# noinspection SpellCheckingInspection
@run.register(IndefiniteArticleObject)
def _(indef: IndefiniteArticleObject):
    formatter = Formatter()
    formatter.add_indefinite_article()
    return formatter

# noinspection PyUnusedLocal
@run.register(DigitObject)
def _(digit: DigitObject):
    formatter = Formatter()
    formatter.append(str(randint(0, 9)))
    return formatter


@run.register(RegexObject)
def _(regex: RegexObject):
    # noinspection SpellCheckingInspection
    formatter = Formatter()

    def repl(matchobj: Match):
        RegexState.match = matchobj.group()
        return run(regex.replacement).resolve()

    formatter.append(sub(regex.regex, repl, run(regex.scope).resolve()))
    return formatter
