# PyPSA → GEMS Parameter Conversion

## System base assumptions

GEMS uses a **1 MW system base** (implicit). All per-unit reactances must be
expressed on this base.

For a bus at nominal voltage `v_nom` [kV]:

```
Z_base = v_nom² [Ω]
```

This means 1 pu impedance = `v_nom²` ohms.

---

## Line

| PyPSA parameter | Unit | GEMS parameter | Unit | Formula |
|---|---|---|---|---|
| `x` | Ω | `x` | pu | `x_pu = x / v_nom²` |
| `s_nom` | MVA | `s_nom_min`, `s_nom_max` | MVA | both = `s_nom` (non-extendable) |
| `s_max_pu` | pu | `s_max_pu` | pu | same value (default 1.0) |
| `capital_cost` | €/MVA | `capital_cost` | €/MVA | same value |

**`v_nom`** is the nominal voltage of the line's buses [kV] (both ends must be
at the same voltage level for a line).

### Example — 110 kV line, x = 0.1 Ω

```
x_pu = 0.1 / 110² = 0.1 / 12100 = 8.264e-6
```

### Example — 1 kV (pu) line, x = 0.1 Ω

```
x_pu = 0.1 / 1² = 0.1   (no conversion needed at v_nom = 1)
```

---

## Transformer

PyPSA stores transformer `x` in **pu on the transformer's own MVA base**.
GEMS needs `x_pu_eff` in **pu on the 1 MW system base**.

| PyPSA parameter | Unit | GEMS parameter | Unit | Formula |
|---|---|---|---|---|
| `x` | pu (on `s_nom` base) | `x_pu_eff` | pu (on 1 MW base) | `x_pu_eff = x / s_nom` |
| `s_nom` | MVA | `s_nom_min`, `s_nom_max` | MVA | both = `s_nom` (non-extendable) |
| `s_max_pu` | pu | `s_max_pu` | pu | same value (default 1.0) |
| `capital_cost` | €/MVA | `capital_cost` | €/MVA | same value |

PyPSA also exposes `x_pu_eff` directly after network setup:

```python
x_pu_eff = network.transformers.loc["T_AB", "x_pu_eff"]
# equivalent to x / s_nom for tap_ratio = 1
```

### Example — 150 MVA transformer, x = 0.10 pu

```
x_pu_eff = 0.10 / 150 = 6.667e-4
```

---

## Reference bus (slack bus, θ = 0)

PyPSA selects the slack bus automatically (first bus in `network.buses.index`
or the bus with `slack=True`).

In GEMS, use the `theta_flag` parameter on the `bus` model:

| Bus role | `theta_flag` value |
|---|---|
| Reference (slack) | `1` |
| All other buses | `0` |

The bus model constraint `theta_flag * theta = 0` enforces θ = 0 only where
`theta_flag = 1`.

Alternatively, connect a `reference_bus` component to the slack bus via
`theta_port`.

---

## Quick-reference formulas

```
# Line reactance (Ω → pu)
x_gems = x_pypsa_ohm / v_nom_kV²

# Transformer reactance (pu on own base → pu on system base)
x_pu_eff = x_pypsa_pu / s_nom_MVA

# Capacity bounds (non-extendable)
s_nom_min = s_nom_max = s_nom_pypsa

# Capacity bounds (extendable)
s_nom_min = s_nom_min_pypsa   (or 0 if not set)
s_nom_max = s_nom_max_pypsa   (or large number if not set)
```
