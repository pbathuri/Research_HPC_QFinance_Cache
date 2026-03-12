"""Simple experiment runner for repeated pricing and basic metrics."""


def run_repeated_pricing_experiment(pricer_factory, num_trials: int) -> dict:
    """Run price_option repeatedly and return summary metrics.

    pricer_factory must be a callable that returns a MonteCarloPricer.
    Returns a dict with num_trials, average_price, average_variance,
    cache_hits, cache_misses, cache_entries.
    """
    pricer = pricer_factory()
    prices = []
    variances = []
    for _ in range(num_trials):
        price, var = pricer.price_option()
        prices.append(price)
        variances.append(var)
    average_price = sum(prices) / num_trials
    average_variance = sum(variances) / num_trials
    if pricer.cache_store is not None:
        s = pricer.cache_store.stats()
        cache_hits = s["hits"]
        cache_misses = s["misses"]
        cache_entries = s["entries"]
    else:
        cache_hits = cache_misses = cache_entries = 0
    return {
        "num_trials": num_trials,
        "average_price": average_price,
        "average_variance": average_variance,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "cache_entries": cache_entries,
    }
