A program to generate PDDL instances for PDDL domains extended with
legality-constraints (and a domain-wide goal) as described in *C. Grundke, G.
Röger, M. Helmert. Formal Representations of Classical Planning Domains. In
Proceedings of the 34th International Conference on Automated Planning and
Scheduling (ICAPS 2024), pp. 239-248. 2024.*

It uses the parser of [Fast Downward](https://github.com/aibasel/downward) to
parse an input domain. The program then translates this domain to an answer set
program and uses [clingo](https://github.com/potassco/clingo) to solve and
generate answer sets for it. Lastly, the program translates the answer sets to
PDDL instances as output.


## Setup

After cloning the repository, the instance generator can be installed via
[pip](https://pip.pypa.io/en/stable/installation/). The [following
section](#recommended-steps) gives a step-by-step explanation for this. 

If you plan to change the code of the instance generator and immediately test
the changes, we recommend installing the instance generator with the `-e`
option of pip, or (installing its dependencies manually and) calling it
directly from the src-folder (`cd src && python3 -m instance_generator`).

### Recommended Steps

Clone the repository:
```
git clone https://github.com/aibasel/instance-generator.git instance-generator
```

Create a virtual environment and activate it (this step is not necessary but
keeps your system clean by capsulating the instance generator and its
dependencies):
```
python3 -m venv --prompt instance-generator-venv instance-generator/.venv
source instance-generator/.venv/bin/activate
```
(You can deactivate the virtual environment with `deactivate`.)

Install the instance generator (and its dependencies):
```
pip install instance-generator/
```

Call the help-message of the instance generator to test the installation:
```
python3 -m instance_generator -h
```


## Usage

Use `-h` or `--help` to see all options of the program. If you installed the
instance generator in a virtual environment (as recommended in the [previous
section](#recommended-steps)) do not forget to activate the environment
(`source instance-generator/.venv/bin/activate`).

**Basic usage:**
```
python3 -m instance_generator <domain-file> -n <universe-size>
```
This generates a single instance where

- `<domain-file>` is the domain file for which an instance is generated, and
- `<universe-size>` is a positive integer that specifies how many objects the
  generated instance shall have.

**Usage with type information and cardinality constraints:**

Instead of giving the number of objects (via `-n`) that the generated instances
shall have you can use the `-c` option. With this option you can give
information about how many objects of certain types the generated instances
shall have and specify cardinality-constraints. This option expects a JSON file
as described in the section [Format of JSON config
File](#format-of-json-config-file). You can find two examples for such JSON
files in the `examples` folder.

Example call:
```
python3 -m instance_generator instance-generator/examples/blocksworld-domain.pddl -c instance-generator/examples/blocksworld-config.json
```


## Representative Instances

With the `--representative` option, the instance generator will generate up to
`num_instances` *representative* instances for a domain. The number of
representative instances is usually much smaller than the total number of
instances of a domain, so we recommend to set `num_instances` to `0` (i. e.,
all possible instances will be generated) in this case.

After generating representative instances, the instance generator will also
output a *representative value* of the generated set of instances. This value
lies in the interval (0, 1] and a high value roughly means that the generated
set of instances represents the given domain well.

The implementation to generate representative instances is based on the paper
*E. Böhl, S. Gaggl, D. Rusovac. Representative Answer Sets: Collecting
Something of Everything. In Proceedings of the 26th European Conference on
Artificial Intelligence (ECAI 2023), pp. 271 - 278. 2023.*


## Format of JSON Config File

If you call the instance generator with the `-c` option (instead of `-n`) it
expects a JSON file of a specific format. With this file you can specify the
*types* of some or all objects that the generated instances will include.
Furthermore, you can specify *cardinality constraints* that the generated
instances will follow, i. e. how many atoms of given predicates shall be
included in the generated instances.

The `examples` folder includes such a JSON config file for the Blocksworld
domain (`blocksworld-universe.json`) and for the Childsnack domain
(`childsnack-universe.json`).

The JSON config file is a [JSON](https://www.json.org/json-en.html) file
with a key `universe` and, optionally, a key `cardinality_constraints`. The
values for both keys are dictionaries that must be structured as follows:

`universe`: The keys are types mentioned in the domain file. Their values are
positive integers that specify how many objects of the corresponding types the
generated instances must have.  
You can use PDDL's generic type "object" if the domain does not use types or if
you want to not require a specific type for some or all objects (i. e., if
the ASP solver should choose the types). 

`cardinality_constraints`: The keys are names of basic predicates mentioned in
the domain file. The values are lists where each list contains two integers
larger or equal to -1. The first integer specifies the (inclusive) lower bound
on the number of atoms of the corresponding predicate that the generated
instances will have (-1 corresponds to the minimal possible value which is
usually 0). The second integer specifies the (inclusive) upper bound (-1
corresponds to the maximal possible value, i. e., $$n^u$$ for $$n$$-ary
predicates over a universe of size $$u$$).

A JSON config file for the Blocksworld domain could for example look like
this:

```
{
  "universe": {
    "object": 5
  },
  "cardinality_constraints": {
    "on-table": [-1,2],
    "on_g": [4,-1]
  }
}
```


## Remarks on Domain Encoding

Although it is not enforced (because it is not required by PDDL), the instance
generator expects the following from domain files:

- The types of parameters of derived predicates are repeated in the axiom heads
  that define the respective derived predicates.
- The types mentioned in an axiom head are consistent with those of the
  corresponding derived predicate from the `:predicate` section (the type is
  identical or the axiom head specifies a subtype).

For example,

```
;; ...

(:predicates
  ;; ...
  (has-some-paint ?r - robot)
)

;; ...

(:axiom (has-some-paint ?r)
  (;; axiom body
  ))
```

could lead to unexpected behaviour of the instance generator because the axiom
head does not repeat the type `robot` of `?r` that is specified for predicate
`has-some-paint` in the `:predicate` section. We recommend to repeat the types
of parameters in axiom heads:

```
;; ...
(:axiom (has-some-paint ?r - robot)
;; ...
```


## Debugging a Domain File

If no instance could be generated and the cause might be the input domain, the
following options might help you debugging the domain:

- `--print_normalized_domain` To print the domain description after it was
  normalized by the preprocessing step (which uses the Fast Downward translator).
- `--print_translated_domain` To print the ASP program that the input domain is
  translated to. This ASP program can be used as input for the ASP solver
  clingo directly. Each ASP model (alias answer set) of this ASP program
  corresponds to one instance that the instance generator can produce.
- `--print_asp_model` To print the ASP models (i. e. answer sets) of the ASP
  program corresponding to the input domain. Each generated instance is
  based on one such ASP model. Compared to the generated instances their
  corresponding ASP models also include helper predicates from the Fast
  Downward translator and the derived predicates.

