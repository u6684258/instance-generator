import contextlib
import sys

from . import graph
from .. import pddl
from .parse_error import ParseError

TYPED_LIST_SEPARATOR = "-"

SYNTAX_LITERAL = "(PREDICATE ARGUMENTS*)"
SYNTAX_LITERAL_NEGATED = "(not (PREDICATE ARGUMENTS*))"
SYNTAX_LITERAL_POSSIBLY_NEGATED = f"{SYNTAX_LITERAL} or {SYNTAX_LITERAL_NEGATED}"

SYNTAX_PREDICATE = "(PREDICATE_NAME [VARIABLE [- TYPE]?]*)"
SYNTAX_PREDICATES = f"(:predicates {SYNTAX_PREDICATE}*)"
SYNTAX_LEGALITY_PREDICATE = "PREDICATE_NAME"
SYNTAX_FUNCTION = "(FUNCTION_NAME [VARIABLE [- TYPE]?]*)"
SYNTAX_ACTION = "(:action NAME [:parameters PARAMETERS]? " \
                "[:precondition PRECONDITION]? :effect EFFECT)"
SYNTAX_AXIOM = "(:derived PREDICATE CONDITION)"
SYNTAX_FORMALIZATION_AXIOM = "(:axiom PREDICATE CONDITION)"
SYNTAX_GOAL = "(:domain-goal GOAL)"

SYNTAX_CONDITION_AND = "(and CONDITION*)"
SYNTAX_CONDITION_OR = "(or CONDITION*)"
SYNTAX_CONDITION_IMPLY = "(imply CONDITION CONDITION)"
SYNTAX_CONDITION_NOT = "(not CONDITION)"
SYNTAX_CONDITION_FORALL_EXISTS = "({forall, exists} VARIABLES CONDITION)"

SYNTAX_EFFECT_FORALL = "(forall VARIABLES EFFECT)"
SYNTAX_EFFECT_WHEN = "(when CONDITION EFFECT)"
SYNTAX_EFFECT_INCREASE = "(increase (total-cost) ASSIGNMENT)"

SYNTAX_EXPRESSION = "POSITIVE_NUMBER or (FUNCTION VARIABLES*)"
SYNTAX_ASSIGNMENT = "({=,increase} EXPRESSION EXPRESSION)"
SYNTAX_DOMAIN_DOMAIN_NAME = "(domain NAME)"

CONDITION_TAG_TO_SYNTAX = {
    "and": SYNTAX_CONDITION_AND,
    "or": SYNTAX_CONDITION_OR,
    "imply": SYNTAX_CONDITION_IMPLY,
    "not": SYNTAX_CONDITION_NOT,
    "forall": SYNTAX_CONDITION_FORALL_EXISTS,
}


class Context:
    def __init__(self):
        self._traceback = []

    def __str__(self) -> str:
        return "\n\t->".join(self._traceback)

    def error(self, message, item=None, syntax=None):
        error_msg = f"{self}\n{message}"
        if syntax:
            error_msg += f"\nSyntax: {syntax}"
        if item:
            error_msg += f"\nGot: {item}"
        raise ParseError(error_msg)

    def expected_word_error(self, name, *args, **kwargs):
        self.error(f"{name} is expected to be a word.", *args, **kwargs)

    def expected_list_error(self, name, *args, **kwargs):
        self.error(f"{name} is expected to be a block.", *args, **kwargs)

    def expected_named_block_error(self, alist, expected, *args, **kwargs):
        self.error(f"Expected a non-empty block starting with any of the "
                   f"following words: {', '.join(expected)}",
                   item=alist, *args, **kwargs)

    @contextlib.contextmanager
    def layer(self, message: str):
        self._traceback.append(message)
        yield
        assert self._traceback.pop() == message


def check_named_block(alist, names):
    return isinstance(alist, list) and alist and alist[0] in names


def assert_named_block(context, alist, names):
    if not check_named_block(alist, names):
        context.expected_named_block_error(alist, names)


def construct_typed_object(context, name, _type):
    with context.layer("Parsing typed object"):
        if not isinstance(name, str):
            context.expected_word_error("Name of typed object", name)
        return pddl.TypedObject(name, _type)


def construct_type(context, curr_type, base_type):
    with context.layer("Parsing PDDL type"):
        if not isinstance(curr_type, str):
            context.expected_word_error("PDDL type", curr_type)
        if not isinstance(base_type, str):
            context.expected_word_error("Base type", base_type)
        return pddl.Type(curr_type, base_type)


def parse_typed_list(context, alist, only_variables=False,
                     constructor=construct_typed_object,
                     default_type="object"):
    with context.layer("Parsing typed list"):
        result = []
        group_number = 1
        while alist:
            with context.layer(f"Parsing {group_number}. group of typed list"):
                try:
                    separator_position = alist.index(TYPED_LIST_SEPARATOR)
                except ValueError:
                    items = alist
                    _type = default_type
                    alist = []
                else:
                    if separator_position == len(alist) - 1:
                        context.error(
                            f"Type missing after '{TYPED_LIST_SEPARATOR}'.",
                            alist)
                    items = alist[:separator_position]
                    _type = alist[separator_position + 1]
                    alist = alist[separator_position + 2:]
                    if not (isinstance(_type, str) or
                           (_type and _type[0] == "either" and
                            all(isinstance(_sub_type, str) for _sub_type in _type[1:]))):
                        context.error("Type value is expected to be a single word "
                                      "or '(either WORD*)")
                for item in items:
                    if only_variables and not item.startswith("?"):
                        context.error("Expected item to be a variable", item)
                    entry = constructor(context, item, _type)
                    result.append(entry)
            group_number += 1
        return result


def set_supertypes(type_list):
    # TODO: This is a two-stage construction, which is perhaps
    # not a great idea. Might need more thought in the future.
    type_name_to_type = {}
    child_types = []
    for type in type_list:
        type.supertype_names = []
        type_name_to_type[type.name] = type
        if type.basetype_name:
            child_types.append((type.name, type.basetype_name))
    for (desc_name, anc_name) in graph.transitive_closure(child_types):
        type_name_to_type[desc_name].supertype_names.append(anc_name)


def parse_requirements(context, alist):
    with context.layer("Parsing requirements"):
        for item in alist:
            if not isinstance(item, str):
                context.expected_word_error("Requirement label", item)
        try:
            return pddl.Requirements(alist)
        except ValueError as e:
            context.error(f"Error in requirements.\n"
                          f"Reason: {e}")


def parse_predicate(context, alist):
    with context.layer("Parsing predicate name"):
        if not alist:
            context.error("Predicate name missing", syntax=SYNTAX_PREDICATE)
        name = alist[0]
        if not isinstance(name, str):
            context.expected_word_error("Predicate name", name)
    with context.layer(f"Parsing arguments of predicate '{name}'"):
        arguments = parse_typed_list(context, alist[1:], only_variables=True)
    return pddl.Predicate(name, arguments)


def parse_predicates(context, alist):
    with context.layer("Parsing predicates"):
        the_predicates = []
        for no, entry in enumerate(alist):
            with context.layer(f"Parsing {no}. predicate"):
                if not isinstance(entry, list):
                    context.error("Invalid predicate definition.",
                                  syntax=SYNTAX_PREDICATE)
                the_predicates.append(parse_predicate(context, entry))
        return the_predicates


def parse_function(context, alist, type_name):
    with context.layer("Parsing function name"):
        if not isinstance(alist, list) or len(alist) == 0:
            context.error("Invalid definition of function.",
                          syntax=SYNTAX_FUNCTION)
        name = alist[0]
        if not isinstance(name, str):
            context.expected_word_error("Function name", name)
    with context.layer(f"Parsing function '{name}'"):
        arguments = parse_typed_list(context, alist[1:])
        if not isinstance(type_name, str):
            context.expected_word_error("Function type", type_name)
    return pddl.Function(name, arguments, type_name)


def parse_condition(context, alist, type_dict, predicate_dict):
    with context.layer("Parsing condition"):
        condition = parse_condition_aux(
            context, alist, False, type_dict, predicate_dict)
        return condition.uniquify_variables({}).simplified()


def parse_condition_aux(context, alist, negated, type_dict, predicate_dict):
    """Parse a PDDL condition. The condition is translated into NNF on the fly."""
    if not alist:
        context.error("Expected a non-empty block as condition.")
    tag = alist[0]
    if tag in ("and", "or", "not", "imply"):
        args = alist[1:]
        if tag == "imply":
            if len(args) != 2:
                context.error("'imply' expects exactly two arguments.",
                              syntax=SYNTAX_CONDITION_IMPLY)
        if tag == "not":
            if len(args) != 1:
                context.error("'not' expects exactly one argument.",
                              syntax=SYNTAX_CONDITION_NOT)
            negated = not negated
    elif tag in ("forall", "exists"):
        if len(alist) != 3:
            context.error("'forall' and 'exists' expect exactly two arguments.",
                          syntax=SYNTAX_CONDITION_FORALL_EXISTS)
        if not isinstance(alist[1], list) or not alist[1]:
            context.error(
                "The first argument (VARIABLES) of 'forall' and 'exists' is "
                "expected to be a non-empty block.",
                syntax=SYNTAX_CONDITION_FORALL_EXISTS
            )
        parameters = parse_typed_list(context, alist[1])
        args = [alist[2]]
    elif tag in predicate_dict or tag in type_dict:
        return parse_literal(context, alist, type_dict, predicate_dict, negated=negated)
    else:
        context.error("Expected logical operator or predicate name", tag)

    for nb_arg, arg in enumerate(args, start=1):
        if not isinstance(arg, list) or not arg:
            context.error(
                f"'{tag}' expects as {nb_arg}. argument a non-empty block.",
                item=arg, syntax=CONDITION_TAG_TO_SYNTAX[tag])

    if tag == "imply":
        parts = [parse_condition_aux(
                context, args[0], not negated, type_dict, predicate_dict),
                 parse_condition_aux(
                context, args[1], negated, type_dict, predicate_dict)]
        tag = "or"
    else:
        parts = [parse_condition_aux(context, part, negated, type_dict, predicate_dict)
                 for part in args]

    if tag == "and" and not negated or tag == "or" and negated:
        return pddl.Conjunction(parts)
    elif tag == "or" and not negated or tag == "and" and negated:
        return pddl.Disjunction(parts)
    elif tag == "forall" and not negated or tag == "exists" and negated:
        return pddl.UniversalCondition(parameters, parts)
    elif tag == "exists" and not negated or tag == "forall" and negated:
        return pddl.ExistentialCondition(parameters, parts)
    elif tag == "not":
        return parts[0]


def parse_literal(context, alist, type_dict, predicate_dict, negated=False):
    with context.layer("Parsing literal"):
        if not alist:
            context.error("Literal definition has to be a non-empty block.",
                          alist, syntax=SYNTAX_LITERAL_POSSIBLY_NEGATED)
        if alist[0] == "not":
            if len(alist) != 2:
                context.error(
                    "Negated literal definition has to have exactly one block as argument.",
                    alist, syntax=SYNTAX_LITERAL_NEGATED)
            alist = alist[1]
            if not isinstance(alist, list) or not alist:
                context.error(
                    "Definition of negated literal has to be a non-empty block.",
                    alist, syntax=SYNTAX_LITERAL)
            negated = not negated

        predicate_name = alist[0]
        if not isinstance(predicate_name, str):
            context.expected_word_error("Predicate name", predicate_name)
        pred_id, arity = _get_predicate_id_and_arity(
            context, predicate_name, type_dict, predicate_dict)

        if arity != len(alist) - 1:
            context.error(f"Predicate '{predicate_name}' of arity {arity} used"
                          f" with {len(alist) - 1} arguments.", alist)

        if negated:
            return pddl.NegatedAtom(pred_id, alist[1:])
        else:
            return pddl.Atom(pred_id, alist[1:])


SEEN_WARNING_TYPE_PREDICATE_NAME_CLASH = False
def _get_predicate_id_and_arity(context, text, type_dict, predicate_dict):
    global SEEN_WARNING_TYPE_PREDICATE_NAME_CLASH

    the_type = type_dict.get(text)
    the_predicate = predicate_dict.get(text)

    if the_type is None and the_predicate is None:
        context.error("Undeclared predicate", text)
    elif the_predicate is not None:
        if the_type is not None and not SEEN_WARNING_TYPE_PREDICATE_NAME_CLASH:
            msg = ("Warning: name clash between type and predicate %r.\n"
                   "Interpreting as predicate in conditions.") % text
            print(msg, file=sys.stderr)
            SEEN_WARNING_TYPE_PREDICATE_NAME_CLASH = True
        return the_predicate.name, the_predicate.get_arity()
    else:
        assert the_type is not None
        return the_type.get_predicate_name(), 1


def analyse_effects(context, alist, result, type_dict, predicate_dict,
                  affected_predicates, condition_predicates):
    """Analyse a PDDL effect (any combination of simple, conjunctive, conditional, and universal)
       for affected predicates."""
    analyse_effect(context, alist, type_dict, predicate_dict,
                   affected_predicates, condition_predicates)


def add_effect(tmp_effect, result):
    """tmp_effect has the following structure:
       [ConjunctiveEffect] [UniversalEffect] [ConditionalEffect] SimpleEffect."""

    if isinstance(tmp_effect, pddl.ConjunctiveEffect):
        for effect in tmp_effect.effects:
            add_effect(effect, result)
        return
    else:
        parameters = []
        condition = pddl.Truth()
        if isinstance(tmp_effect, pddl.UniversalEffect):
            parameters = tmp_effect.parameters
            if isinstance(tmp_effect.effect, pddl.ConditionalEffect):
                condition = tmp_effect.effect.condition
                assert isinstance(tmp_effect.effect.effect, pddl.SimpleEffect)
                effect = tmp_effect.effect.effect.effect
            else:
                assert isinstance(tmp_effect.effect, pddl.SimpleEffect)
                effect = tmp_effect.effect.effect
        elif isinstance(tmp_effect, pddl.ConditionalEffect):
            condition = tmp_effect.condition
            assert isinstance(tmp_effect.effect, pddl.SimpleEffect)
            effect = tmp_effect.effect.effect
        else:
            assert isinstance(tmp_effect, pddl.SimpleEffect)
            effect = tmp_effect.effect
        assert isinstance(effect, pddl.Literal)
        # Check for contradictory effects
        condition = condition.simplified()
        new_effect = pddl.Effect(parameters, condition, effect)
        contradiction = pddl.Effect(parameters, condition, effect.negate())
        if contradiction not in result:
            result.append(new_effect)
        else:
            # We use add-after-delete semantics, keep positive effect
            if isinstance(contradiction.literal, pddl.NegatedAtom):
                result.remove(contradiction)
                result.append(new_effect)


def analyse_effect(context, alist, type_dict, predicate_dict,
                   affected_predicates, condition_predicates):
    tag = alist[0]
    if tag == "and":
        effects = []
        for eff in alist[1:]:
            analyse_effect(context, eff, type_dict, predicate_dict,
                           affected_predicates, condition_predicates)
    elif tag == "forall":
        analyse_effect(context, alist[2], type_dict, predicate_dict,
                       affected_predicates, condition_predicates)
    elif tag == "when":
        condition = parse_condition(context, alist[1], type_dict,
                                    predicate_dict)
        condition_predicates |= condition.predicates()
        analyse_effect(context, alist[2], type_dict, predicate_dict,
                       affected_predicates, condition_predicates)
    elif tag != "increase":
        affected = parse_literal(context, alist, {}, predicate_dict)
        affected_predicates.add(affected.predicate)



def parse_expression(context, exp):
    with context.layer("Parsing expression"):
        if isinstance(exp, list):
            if len(exp) < 1:
                context.error("Expression cannot be an empty block.",
                              syntax=SYNTAX_EXPRESSION)
            functionsymbol = exp[0]
            return pddl.PrimitiveNumericExpression(functionsymbol, exp[1:])
        elif exp.replace(".", "").isdigit() and exp.count(".") <= 1:
            return pddl.NumericConstant(float(exp))
        elif exp[0] == "-":
            context.error("Expression cannot be a negative number",
                          syntax=SYNTAX_EXPRESSION)
        else:
            return pddl.PrimitiveNumericExpression(exp, [])


def parse_assignment(context, alist):
    with context.layer("Parsing Assignment"):
        if len(alist) != 3:
            context.error("Assignment expects two arguments",
                          syntax=SYNTAX_ASSIGNMENT)
        op = alist[0]
        head = parse_expression(context, alist[1])
        exp = parse_expression(context, alist[2])
        if op == "=":
            return pddl.Assign(head, exp)
        elif op == "increase":
            return pddl.Increase(head, exp)
        else:
            context.error(f"Unsupported assignment operator '{op}'."
                          f" Use '=' or 'increase'.")


# only determines what predicates are affected by the action and adds these predicate
# names to parameter affected_predicates.
def analyse_action(context, alist, type_dict, predicate_dict,
                   affected_predicates, condition_predicates):
        iterator = iter(alist)
        action_tag = next(iterator)
        name = next(iterator)
        parameters_tag_opt = next(iterator)
        if parameters_tag_opt == ":parameters":
            next(iterator)
            precondition_tag_opt = next(iterator)
        else:
            precondition_tag_opt = parameters_tag_opt
        if precondition_tag_opt == ":precondition":
            precondition_list = next(iterator)
            precondition = parse_condition(
                context, precondition_list, type_dict, predicate_dict)
            condition_predicates |= precondition.predicates()
            next(iterator)
        effect_list = next(iterator)
        eff = []
        if effect_list:
            analyse_effects(context, effect_list, eff, type_dict, predicate_dict,
                          affected_predicates, condition_predicates)


def parse_axiom(context, alist, type_dict, predicate_dict, legality):
    with context.layer("Parsing derived predicate"):
        if len(alist) != 3:
            context.error("Expecting block with exactly three elements",
                          syntax=SYNTAX_AXIOM)
        assert alist[0] in (":derived", ":axiom")
        if not isinstance(alist[1], list):
            context.expected_list_error("The first argument (PREDICATE)",
                                        syntax=SYNTAX_AXIOM)
        predicate = parse_predicate(context, alist[1])
    with context.layer(f"Parsing condition for derived predicate '{predicate}'"):
        if not isinstance(alist[2], list):
            context.error("The second argument (CONDITION) is expected to be a block.",
                          syntax=SYNTAX_AXIOM)
        condition = parse_condition(
            context, alist[2], type_dict, predicate_dict)
        return pddl.Axiom(predicate.name, predicate.arguments,
                          len(predicate.arguments), condition, legality)


def parse_axioms_and_analyse_actions(context, entries, type_dict,
                                     predicate_dict):
    the_axioms = []
    affected_preds = set()
    condition_predicates = set()
    for no, entry in enumerate(entries, start=1):
        with context.layer(f"Parsing {no}. axiom/action entry"):
            assert_named_block(context, entry, [":derived", ":action", ":axiom"])
            if entry[0] in (":derived", ":axiom"):
                legality = True if entry[0] == ":axiom" else False
                with context.layer(f"Parsing {len(the_axioms) + 1}. axiom"):
                    the_axioms.append(parse_axiom(
                        context, entry, type_dict, predicate_dict,
                        legality))
                    if entry[0] == ":derived":
                        condition_predicates |= \
                        the_axioms[-1].condition.predicates()
            else:
                assert entry[0] == ":action"
                analyse_action(context, entry, type_dict, predicate_dict,
                               affected_preds, condition_predicates)
    return the_axioms, affected_preds, condition_predicates


def parse_domain(domain_pddl):
    context = Context()
    if not isinstance(domain_pddl, list):
        context.error("Invalid definition of a PDDL domain.")
    domain_name, domain_requirements, types, type_dict, constants, predicates, \
        predicate_dict, functions, legality_predicate, goal, axioms, \
        affected_predicates, condition_predicates = parse_domain_pddl(context, domain_pddl)

    requirements = pddl.Requirements(sorted(set(
                domain_requirements.requirements)))

    return pddl.Domain(
        domain_name, legality_predicate, requirements, types, constants,
        predicates, functions, goal, axioms, affected_predicates,
        condition_predicates)


def parse_domain_pddl(context, domain_pddl):
    iterator = iter(domain_pddl)
    with context.layer("Parsing domain"):
        define_tag = next(iterator)
        if define_tag != "define":
            context.error(f"Domain definition expected to start with '(define '. Got '({define_tag}'")

        with context.layer("Parsing domain name"):
            domain_line = next(iterator)
            if (not check_named_block(domain_line, ["domain"]) or
                    len(domain_line) != 2 or not isinstance(domain_line[1], str)):
                context.error("Invalid definition of domain name.",
                              syntax=SYNTAX_DOMAIN_DOMAIN_NAME)
            yield domain_line[1]

        ## We allow an arbitrary order of the requirement, types, constants,
        ## predicates and functions specification. The PDDL BNF is more strict on
        ## this, so we print a warning if it is violated.
        requirements = pddl.Requirements([":strips"])
        the_types = [pddl.Type("object")]
        type_dict = {type.name: type for type in the_types}
        constants, the_predicates, the_functions = [], [], []
        predicate_dict, the_legality_predicate = None, None
        correct_order = [":requirements", ":types", ":constants", ":predicates",
                         ":functions", ":legality-predicate", ":domain-goal"]
        action_or_axiom_block = [":derived", ":action"]
        seen_fields = []
        first_action = None
        for opt in iterator:
            assert_named_block(context, opt, correct_order + action_or_axiom_block)
            field = opt[0]
            if field not in correct_order:
                first_action = opt
                break
            if field in seen_fields:
                context.error(f"Error in domain specification\n"
                              f"Reason: two '{field}' specifications.")
            if (seen_fields and
                correct_order.index(seen_fields[-1]) > correct_order.index(field)):
                msg = f"\nWarning: {field} specification not allowed here (cf. PDDL BNF)"
                print(msg, file=sys.stderr)
            seen_fields.append(field)
            if field == ":requirements":
                requirements = parse_requirements(context, opt[1:])
            elif field == ":types":
                with context.layer("Parsing types"):
                    the_types.extend(parse_typed_list(
                            context, opt[1:], constructor=construct_type))
                type_dict = {type.name: type for type in the_types}
            elif field == ":constants":
                with context.layer("Parsing constants"):
                    constants = parse_typed_list(context, opt[1:])
            elif field == ":predicates":
                the_predicates = parse_predicates(context, opt[1:])
                the_predicates += [pddl.Predicate("=", [
                        pddl.TypedObject("?x", "object"),
                        pddl.TypedObject("?y", "object")]),
                    pddl.Predicate("<", [
                        pddl.TypedObject("?x", "object"),
                        pddl.TypedObject("?y", "object")])]
                predicate_dict = {pred.name: pred for pred in the_predicates}
            elif field == ":functions":
                with context.layer("Parsing functions"):
                    the_functions = parse_typed_list(
                        context, opt[1:],
                        constructor=parse_function,
                        default_type="number")
            elif field == ":legality-predicate":
                the_legality_predicate = opt[1]
                if the_legality_predicate not in predicate_dict:
                    context.error("legality predicate not among declared"
                                  "predicates", the_legality_predicate)
            elif field == ":domain-goal":
                goal = opt
                with context.layer("Parsing domain goal"):
                    if (not check_named_block(goal, [":domain-goal"]) or
                            len(goal) != 2 or not isinstance(goal[1], list) or
                            not goal[1]):
                        context.error("Expected non-empty domain goal.", syntax=SYNTAX_GOAL)
                    the_goal = parse_condition(context, goal[1], type_dict, predicate_dict)
        set_supertypes(the_types)
        yield requirements
        yield the_types
        yield type_dict
        yield constants
        yield the_predicates
        yield predicate_dict
        yield the_functions
        yield the_legality_predicate
        yield the_goal

        entries = []
        if first_action is not None:
            entries.append(first_action)
        entries.extend(iterator)

        the_axioms, affected_predicates, condition_predicates = \
                parse_axioms_and_analyse_actions(context, entries, type_dict, predicate_dict)

        yield the_axioms
        yield affected_predicates
        yield condition_predicates
