Program to generate PDDL instances for PDDL domains extended with axioms (and a
domain-wide goal) as described in *C. Grundke, G. Röger, M. Helmert. Formal
Representations of Classical Planning Domains. In Proceedings of the 34th
International Conference on Automated Planning and Scheduling (ICAPS 2024), pp.
239-248. 2024.*

**TODO** explain basic pipeline and cite clingo

## Usage

- `-h` or `--help` to see all options of the program
- most simple usage: `./instance_generation.py <domain-file> -n <universe-size>`
  - `<domain-file>` is the path to the PDDL domain file for which an instance
    will be generated
  - `<universe-size>` is a positive integer that specifies how many objects the
    generated instance will have
- **TODO** add example domain (blocksworld, or floortile because of types) and
  example JSDON-file to repo, and explain how could for example call program
  for them


## Format of extended-input file

JSON file with a key `universe` and, optionally, a key
`cardinality_constraints`. The values for both keys are dictionaries that must
be structured as follows:

`universe`: The keys are types mentioned in the PDDL domain file (use PDDL's
generic type "object" if the domain does not use types or if one wishes to not
require a specific type). Their values are positive integers that specify how
many objects of the corresponding types the generated instances will have

`cardinality_constraints`: The keys are names of basic predicates mentioned in
the PDDL domain file. The values are lists where each list contains two
integers larger or equal to -1. The first integer specifies the (inclusive)
lower bound on the number of atoms of the corresponding predicate that the
generated instances will have (-1 corresponds to the minimal possible value
which is usually 0). The second integer specifies the (inclusive) upper bound
(-1 corresponds to the maximal possible value, i. e., $$n^u$$ for $$n$$-ary
predicates over a universe of size $$u$$).

An extended-input file for the blocksworld domain could for example look like
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


## Remarks

Although it is not enforced (because it is not required by PDDL), the instance
generator expects the following:

- The types of parameters of derived predicates are repeated in the axiom heads
  that define the respective derived predicates, and
- the types mentioned in an axiom head are the same as the ones mentioned for
  the corresponding derived predicate in the `:predicate` section.

For example,

```
; ...

(:predicates
  ;; ...
  (has-some-paint ?r - robot)
)

;; ...

(:axiom (has-some-paint ?r)
  (exists (?c - color) (robot-has ?r ?c)))
```

can lead to unexpected behaviour of the instance generator. We recommend to
repeat the types of parameters in axiom heads:

```
;; ...
(:axiom (has-some-paint ?r - robot)
;; ...
```

