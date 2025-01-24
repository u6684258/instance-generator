object(1).
object(2).
object(3).
object(4).
object(5).
{object(Var_1); robot(Var_1); tile(Var_1); color(Var_1); robot_DASH_at(Var_1, Var_2); up(Var_1, Var_2); down(Var_1, Var_2); right(Var_1, Var_2); left(Var_1, Var_2); clear(Var_1); painted(Var_1, Var_2); robot_DASH_has(Var_1, Var_2); available_DASH_color(Var_1); free_DASH_color(Var_1); painted_g(Var_1, Var_2)} :- object(Var_1), object(Var_2).
legal() :- not illegal().
illegal() :- not new_DASH_axiom_AT_0(R), robot(R).
illegal() :- robot_DASH_at(R, T1), robot_DASH_at(R, T2), T1 != T2, robot(R), tile(T1), tile(T2).
illegal() :- not clear(T), not new_DASH_axiom_AT_1(T), not new_DASH_axiom_AT_2(T), tile(T).
illegal() :- not new_DASH_axiom_AT_3().
illegal() :- not new_DASH_axiom_AT_4().
illegal() :- X != Y, X != Z, Y != Z, color(X), color(Y), color(Z).
illegal() :- not new_DASH_axiom_AT_5(R), robot(R).
illegal() :- not available_DASH_color(C), color(C).
illegal() :- painted(T, C), tile(T), color(C).
illegal() :- up(X, Y), not down(Y, X), tile(X), tile(Y).
illegal() :- down(X, Y), not up(Y, X), tile(X), tile(Y).
illegal() :- left(X, Y), not right(Y, X), tile(X), tile(Y).
illegal() :- right(X, Y), not left(Y, X), tile(X), tile(Y).
illegal() :- up(X, X), tile(X).
illegal() :- down(X, X), tile(X).
illegal() :- left(X, X), tile(X).
illegal() :- right(X, X), tile(X).
illegal() :- up(X, Y), up(X, Z), Y != Z, tile(X), tile(Y), tile(Z).
illegal() :- down(X, Y), down(X, Z), Y != Z, tile(X), tile(Y), tile(Z).
illegal() :- left(X, Y), left(X, Z), Y != Z, tile(X), tile(Y), tile(Z).
illegal() :- right(X, Y), right(X, Z), Y != Z, tile(X), tile(Y), tile(Z).
tl(X) :- not new_DASH_axiom_AT_6(X), tile(X).
illegal() :- not new_DASH_axiom_AT_7().
illegal() :- tl(X), tl(Y), X != Y, tile(X), tile(Y).
col(X) :- tl(X), tile(X).
col(X) :- col(Y), right(X, Y), tile(X), tile(Y).
colof(X, C) :- col(C), X = C, tile(X), tile(C).
colof(X, C) :- colof(Y, C), down(X, Y), tile(X), tile(C), tile(Y).
row(X) :- tl(X), tile(X).
row(X) :- row(Y), down(X, Y), tile(X), tile(Y).
rowof(X, R) :- row(R), X = R, tile(X), tile(R).
rowof(X, R) :- rowof(Y, R), right(X, Y), tile(X), tile(R), tile(Y).
illegal() :- col(C), row(R), not new_DASH_axiom_AT_8(C, R), tile(C), tile(R).
illegal() :- colof(X, C), rowof(X, R), colof(Y, C), rowof(Y, R), X != Y, tile(X), tile(Y), tile(C), tile(R).
illegal() :- C1 != C2, colof(X, C1), colof(X, C2), tile(X), tile(C1), tile(C2).
illegal() :- R1 != R2, rowof(X, R1), rowof(X, R2), tile(X), tile(R1), tile(R2).
illegal() :- not one_DASH_col_DASH_grid(), right(Y1, X), down(Z, Y1), not new_DASH_axiom_AT_12(X, Z), tile(X), tile(Y1), tile(Z).
illegal() :- not one_DASH_col_DASH_grid(), down(Y1, X), right(Z, Y1), not new_DASH_axiom_AT_13(X, Z), tile(X), tile(Y1), tile(Z).
illegal() :- not new_DASH_axiom_AT_14(X), tile(X).
illegal() :- R1 != R2, colof(T1, C), colof(T2, C), robot_DASH_at(R1, T1), robot_DASH_at(R2, T2), robot(R1), robot(R2), tile(T1), tile(T2), tile(C).
illegal() :- down(X, Y), not new_DASH_axiom_AT_15(X), tile(X), tile(Y).
illegal() :- not new_DASH_axiom_AT_16(X), painted_g(X, C), tile(X), color(C).
new_DASH_axiom_AT_0(R) :- robot_DASH_at(R, T), robot(R), tile(T).
new_DASH_axiom_AT_1(T) :- robot_DASH_at(R, T), tile(T), object(R).
new_DASH_axiom_AT_2(T) :- painted(T, C), tile(T), object(C).
new_DASH_axiom_AT_3() :- robot_DASH_at(R, T), tile(T), robot(R).
new_DASH_axiom_AT_4() :- X != Y, color(X), color(Y).
new_DASH_axiom_AT_5(R) :- robot_DASH_has(R, C), robot(R), color(C).
new_DASH_axiom_AT_7() :- tl(X), tile(X).
new_DASH_axiom_AT_8(C, R) :- colof(X, C), rowof(X, R), tile(C), tile(R), object(X).
new_DASH_axiom_AT_9(X) :- colof(X, C), tile(X), tile(C).
new_DASH_axiom_AT_10(X) :- rowof(X, R), tile(X), tile(R).
new_DASH_axiom_AT_12(X, Z) :- down(Y2, X), right(Z, Y2), tile(X), tile(Z), tile(Y2).
new_DASH_axiom_AT_13(X, Z) :- right(Y2, X), down(Z, Y2), tile(X), tile(Z), tile(Y2).
new_DASH_axiom_AT_15(X) :- painted_g(X, C), tile(X), color(C).
new_DASH_axiom_AT_16(X) :- down(X, Y), tile(X), tile(Y).
illegal() :- clear(T), robot_DASH_at(R, T), tile(T), robot(R), color(C).
illegal() :- clear(T), painted(T, C), tile(T), robot(R), color(C).
illegal() :- not new_DASH_axiom_AT_9(X), tile(X).
illegal() :- not new_DASH_axiom_AT_10(X), tile(X).
one_DASH_col_DASH_grid() :- not new_DASH_axiom_AT_11(), down(T1, T2), tile(T1), tile(T2).
one_DASH_col_DASH_grid() :- not new_DASH_axiom_AT_11(), up(T1, T2), tile(T1), tile(T2).
illegal() :- painted_g(X, C), painted_g(Y, C), up(X, Y), tile(X), tile(Y), color(C).
illegal() :- painted_g(X, C), painted_g(Y, C), down(X, Y), tile(X), tile(Y), color(C).
illegal() :- painted_g(X, C), painted_g(Y, C), left(X, Y), tile(X), tile(Y), color(C).
illegal() :- painted_g(X, C), painted_g(Y, C), right(X, Y), tile(X), tile(Y), color(C).
new_DASH_axiom_AT_6(X) :- up(Y, X), tile(X), tile(Y).
new_DASH_axiom_AT_6(X) :- left(Y, X), tile(X), tile(Y).
new_DASH_axiom_AT_11() :- right(T11, T21), tile(T11), tile(T21).
new_DASH_axiom_AT_11() :- left(T11, T21), tile(T11), tile(T21).
new_DASH_axiom_AT_14(X) :- left(X, Y), tile(X), tile(Y).
new_DASH_axiom_AT_14(X) :- right(X, Y), tile(X), tile(Y).
new_DASH_axiom_AT_14(X) :- down(X, Y), tile(X), tile(Y).
new_DASH_axiom_AT_14(X) :- up(X, Y), tile(X), tile(Y).
:- robot_DASH_at(R, X), not robot(R).
:- robot_DASH_at(R, X), not tile(X).
:- up(X, Y), not tile(X).
:- up(X, Y), not tile(Y).
:- down(X, Y), not tile(X).
:- down(X, Y), not tile(Y).
:- right(X, Y), not tile(X).
:- right(X, Y), not tile(Y).
:- left(X, Y), not tile(X).
:- left(X, Y), not tile(Y).
:- clear(X), not tile(X).
:- painted(X, C), not tile(X).
:- painted(X, C), not color(C).
:- robot_DASH_has(R, C), not robot(R).
:- robot_DASH_has(R, C), not color(C).
:- available_DASH_color(C), not color(C).
:- free_DASH_color(R), not robot(R).
:- painted_g(X, C), not tile(X).
:- painted_g(X, C), not color(C).
:- robot(X), not object(X).
:- tile(X), not object(X).
:- color(X), not object(X).
:- color(X), tile(X).
:- color(X), robot(X).
:- tile(X), robot(X).
:- not legal().
#show object/1.
#show robot/1.
#show tile/1.
#show color/1.
#show robot_DASH_at/2.
#show up/2.
#show down/2.
#show right/2.
#show left/2.
#show clear/1.
#show painted/2.
#show robot_DASH_has/2.
#show available_DASH_color/1.
#show free_DASH_color/1.
#show painted_g/2.

