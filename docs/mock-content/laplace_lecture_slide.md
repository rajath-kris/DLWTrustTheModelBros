# Mock Lecture Slide: Laplace Transform Basics

## Learning objective
Use Laplace transforms to convert linear ODEs with initial conditions into algebraic equations in the `s` domain.

## Core recall
- `\mathcal{L}{f(t)} = F(s)`
- `\mathcal{L}{f'(t)} = sF(s) - f(0)`
- `\mathcal{L}{f''(t)} = s^2F(s) - sf(0) - f'(0)`

## Worked setup (not solved)
Given:
`y'' + 3y' + 2y = e^{-t}`
with `y(0)=1`, `y'(0)=0`

Set up in `s` domain by applying Laplace transform to each term and substituting initial values before solving for `Y(s)`.

## Common mistakes to catch
1. Dropping the initial condition terms when transforming derivatives.
2. Mixing `\mathcal{L}^{-1}` too early before isolating `Y(s)`.
3. Skipping partial fractions when required for inversion.
