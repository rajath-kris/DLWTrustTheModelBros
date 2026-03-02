# Mock Tutorial: Same Concept (Laplace Transform)

## Practice question
For
`y'' + 3y' + 2y = e^{-t}`, `y(0)=1`, `y'(0)=0`:

1. Write the transformed equation in `s`.
2. Identify where initial conditions appear in the transformed expression.
3. Describe the algebraic step you would take before applying inverse Laplace.

## Intended learner response pattern
- Correct: explicitly includes `-sy(0)-y'(0)` in `\mathcal{L}{y''}` and `-y(0)` in `\mathcal{L}{y'}`.
- Misconception: treats transformed derivatives as only `s^n Y(s)` terms.

## Socratic probe examples
- "Which derivative term should contribute `-sy(0)-y'(0)` here?"
- "What changes in your equation if `y(0)` is substituted before rearranging?"
