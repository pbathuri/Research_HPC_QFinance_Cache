"""Monte Carlo pricer."""

from qhpc_cache.config import get_default_config
from qhpc_cache.cache_policy import HeuristicCachePolicy
from qhpc_cache import (
    MonteCarloPricer,
    AIAssistedCachePolicy,
    SimpleCacheStore,
    run_repeated_pricing_experiment,
)

if __name__ == "__main__":
    cfg = get_default_config()

    print("--- AI-assisted policy demo ---")
    policy = AIAssistedCachePolicy()
    cache_store = SimpleCacheStore()
    pricer = MonteCarloPricer(
        cfg.S0,
        cfg.K,
        cfg.r,
        cfg.sigma,
        cfg.T,
        cfg.num_paths,
        policy,
        cache_store,
    )
    # First run: compute and store (cache miss)
    price1, var1 = pricer.price_option()
    print("First run (compute):")
    print(f"  Estimated option price: {price1:.4f}")
    print(f"  Variance of payoffs: {var1:.6f}")

    # Second run: same params, reuse cache (cache hit)
    price2, var2 = pricer.price_option()
    print("Second run (from cache):")
    print(f"  Estimated option price: {price2:.4f}")
    print(f"  Variance of payoffs: {var2:.6f}")

    print("Cache stats:", cache_store.stats())

    # Repeated pricing experiment (fresh pricer + cache per experiment)
    def make_pricer():
        store = SimpleCacheStore()
        return MonteCarloPricer(
            cfg.S0,
            cfg.K,
            cfg.r,
            cfg.sigma,
            cfg.T,
            cfg.num_paths,
            policy,
            store,
        )

    num_trials = 500000000000
    metrics = run_repeated_pricing_experiment(make_pricer, num_trials)
    print("\nRepeated pricing experiment:")
    print(f"  num_trials:      {metrics['num_trials']}")
    print(f"  average_price:  {metrics['average_price']:.4f}")
    print(f"  average_variance: {metrics['average_variance']:.6f}")
    print(f"  cache_hits:     {metrics['cache_hits']}")
    print(f"  cache_misses:   {metrics['cache_misses']}")
    print(f"  cache_entries:  {metrics['cache_entries']}")

    print("\n--- Heuristic policy demo ---")
    heuristic_policy = HeuristicCachePolicy()
    heuristic_store = SimpleCacheStore()
    heuristic_pricer = MonteCarloPricer(
        cfg.S0,
        cfg.K,
        cfg.r,
        cfg.sigma,
        cfg.T,
        cfg.num_paths,
        heuristic_policy,
        heuristic_store,
    )
    p1, v1 = heuristic_pricer.price_option()
    print("First run (compute):")
    print(f"  Estimated option price: {p1:.4f}, variance: {v1:.6f}")
    p2, v2 = heuristic_pricer.price_option()
    print("Second run (from cache):")
    print(f"  Estimated option price: {p2:.4f}, variance: {v2:.6f}")
    print("Cache stats:", heuristic_store.stats())
