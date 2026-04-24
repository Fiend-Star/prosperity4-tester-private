# Per-product position limits. Unknown products default to 80 in test_runner
# (matches the universal R0–R2 limit; extend this dict explicitly for R3+ if
# a new product ships with a non-80 cap).
LIMITS = {
    # Round 1
    "ASH_COATED_OSMIUM": 80,
    "INTARIAN_PEPPER_ROOT": 80,
    # Round 3 delta-1
    "HYDROGEL_PACK": 200,
    "VELVETFRUIT_EXTRACT": 200,
    # Round 3 vouchers (call options on VELVETFRUIT_EXTRACT, TTE 5d at R3 start)
    "VEV_4000": 300,
    "VEV_4500": 300,
    "VEV_5000": 300,
    "VEV_5100": 300,
    "VEV_5200": 300,
    "VEV_5300": 300,
    "VEV_5400": 300,
    "VEV_5500": 300,
    "VEV_6000": 300,
    "VEV_6500": 300,
}