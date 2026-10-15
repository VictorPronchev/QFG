# QFG Dynamics 0.9.0-alpha — test report

Command:

```text
python tests/run_pure_tests.py
```

Result:

```text
QFG Dynamics 0.9.0 Alpha pure numerical + Atlas B5 constraint regression tests: PASS
```

B5-specific assertions cover:

- fixed/movable pair connectivity;
- bounded convergence to captured pair distance;
- captured radial-shell preservation;
- angular-cone projection;
- C3 group reconstruction from captured anchors;
- symmetry-equivalent final pair angles;
- collective polar-tilt freedom (final pair angle is not forced back to the
  captured angle);
- exclusion of `REJECTED` geometry.

The full pre-existing core, dynamics, molecular, B1, B2, B3 and B4 numerical
regression suite remains in the same test executable.
