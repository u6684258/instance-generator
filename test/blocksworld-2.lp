object(1).
object(2).
{clear(Var_1); on_DASH_table(Var_1); arm_DASH_empty(); holding(Var_1); on(Var_1, Var_2); clear_g(Var_1); on_DASH_table_g(Var_1); on_g(Var_1, Var_2)} :- object(Var_1), object(Var_2).
legal() :- not illegal().
illegal() :- above(B, B), object(B).
illegal() :- on(X, Y), on(X, Z), Y != Z, object(X), object(Y), object(Z).
illegal() :- on(Y, X), on(Z, X), Y != Z, object(X), object(Y), object(Z).
illegal() :- not on_DASH_table(X), not new_DASH_axiom_AT_0(X), object(X).
illegal() :- on_DASH_table(X), on(X, Y), object(X), object(Y).
illegal() :- not clear(X), not new_DASH_axiom_AT_1(X), object(X).
illegal() :- clear(X), on(Y, X), object(X), object(Y).
illegal() :- above_g(B, B), object(B).
illegal() :- on_g(X, Y), on_g(X, Z), Y != Z, object(X), object(Y), object(Z).
illegal() :- on_g(Y, X), on_g(Z, X), Y != Z, object(X), object(Y), object(Z).
illegal() :- not on_DASH_table_g(X), not new_DASH_axiom_AT_2(X), object(X).
illegal() :- on_DASH_table_g(X), on_g(X, Y), object(X), object(Y).
illegal() :- not clear_g(X), not new_DASH_axiom_AT_3(X), object(X).
illegal() :- clear_g(X), on_g(Y, X), object(X), object(Y).
new_DASH_axiom_AT_0(X) :- on(X, Y), object(X), object(Y).
new_DASH_axiom_AT_1(X) :- on(Y, X), object(X), object(Y).
new_DASH_axiom_AT_2(X) :- on_g(X, Y), object(X), object(Y).
new_DASH_axiom_AT_3(X) :- on_g(Y, X), object(X), object(Y).
above(X, Y) :- on(X, Y), object(X), object(Y).
above(X, Y) :- on(X, Z), above(Z, Y), object(X), object(Y), object(Z).
illegal() :- not arm_DASH_empty().
illegal() :- holding(X), object(X).
above_g(X, Y) :- on_g(X, Y), object(X), object(Y).
above_g(X, Y) :- on_g(X, Z), above_g(Z, Y), object(X), object(Y), object(Z).
:- clear(X), not object(X).
:- on_DASH_table(X), not object(X).
:- holding(X), not object(X).
:- on(X, Y), not object(X).
:- on(X, Y), not object(Y).
:- clear_g(X), not object(X).
:- on_DASH_table_g(X), not object(X).
:- on_g(X, Y), not object(X).
:- on_g(X, Y), not object(Y).
:- not legal().
#show object/1.
#show clear/1.
#show on_DASH_table/1.
#show arm_DASH_empty/0.
#show holding/1.
#show on/2.
#show clear_g/1.
#show on_DASH_table_g/1.
#show on_g/2.

