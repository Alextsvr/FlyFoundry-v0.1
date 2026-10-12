# Exploratory sensitivity check (NOT used to tune the main comparison)

3 seeds, 40 generations, pop 100, mean of last 5 generations: (held-out QD, train mean fitness). Defaults were fixed before this check.

```
default            A_plastic (0.179,-0.121)  A_noplast (0.206,-0.145)  B_ann (0.333, 0.225)
kc_active 8        A_plastic (0.230,-0.041)  A_noplast (0.211,-0.035)  B_ann (0.333, 0.225)
kc_active 16       A_plastic (0.195,-0.020)  A_noplast (0.209,-0.007)  B_ann (0.333, 0.225)
n_kc 128           A_plastic (0.165,-0.109)  A_noplast (0.168,-0.162)  B_ann (0.333, 0.226)
w_init_std 0.2     A_plastic (0.149,-0.031)  A_noplast (0.126,-0.125)  B_ann (0.333, 0.225)
eta 0.1            A_plastic (0.180,-0.173)  A_noplast (0.206,-0.145)  B_ann (0.333, 0.225)
eta 2.0            A_plastic (0.194,-0.098)  A_noplast (0.206,-0.145)  B_ann (0.333, 0.225)
explore_sigma 0.2  A_plastic (0.204,-0.025)  A_noplast (0.220,-0.115)  B_ann (0.338, 0.249)
mut_sigma_rel 0.1  A_plastic (0.187,-0.117)  A_noplast (0.206,-0.055)  B_ann (0.336, 0.235)
```

Reading: no variant of the sparse mushroom-body-inspired controller approached the evolved ANN on this task within 40 generations. Likely reason (hypothesis, untested): top-k sparse codes make the output a lookup over ~64 KC patterns, so evolution must tune many entries independently.
