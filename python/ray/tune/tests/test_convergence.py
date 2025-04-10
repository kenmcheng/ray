import math
import sys
import unittest

import numpy as np
import pytest

import ray
from ray import tune
from ray.tune.search import ConcurrencyLimiter
from ray.tune.stopper import ExperimentPlateauStopper


def loss(config):
    x = config.get("x")
    tune.report({"loss": x**2})  # A simple function to optimize


class ConvergenceTest(unittest.TestCase):
    """Test convergence in gaussian process."""

    @classmethod
    def setUpClass(cls) -> None:
        ray.init(local_mode=False, num_cpus=1, num_gpus=0)

    @classmethod
    def tearDownClass(cls) -> None:
        ray.shutdown()

    def _testConvergence(self, searcher, top=3, patience=20):
        # This is the space of parameters to explore
        space = {"x": tune.uniform(0, 20)}

        resources_per_trial = {"cpu": 1, "gpu": 0}

        analysis = tune.run(
            loss,
            metric="loss",
            mode="min",
            stop=ExperimentPlateauStopper(metric="loss", top=top, patience=patience),
            search_alg=searcher,
            config=space,
            num_samples=max(100, patience),  # Number of iterations
            resources_per_trial=resources_per_trial,
            raise_on_failed_trial=False,
            fail_fast=True,
            reuse_actors=True,
            verbose=1,
        )
        print(
            f"Num trials: {len(analysis.trials)}. "
            f"Best result: {analysis.best_config['x']}"
        )

        return analysis

    @unittest.skip("ax warm start tests currently failing (need to upgrade ax)")
    def testConvergenceAx(self):
        from ray.tune.search.ax import AxSearch

        np.random.seed(0)

        searcher = AxSearch()
        analysis = self._testConvergence(searcher, patience=10)

        assert math.isclose(analysis.best_config["x"], 0, abs_tol=1e-5)

    def testConvergenceBayesOpt(self):
        from ray.tune.search.bayesopt import BayesOptSearch

        np.random.seed(0)

        # Following bayesian optimization
        searcher = BayesOptSearch(random_search_steps=10)
        searcher.repeat_float_precision = 5
        searcher = ConcurrencyLimiter(searcher, 1)

        analysis = self._testConvergence(searcher, patience=100)

        assert len(analysis.trials) < 50
        assert math.isclose(analysis.best_config["x"], 0, abs_tol=1e-5)

    @pytest.mark.skipif(
        sys.version_info >= (3, 12), reason="HEBO doesn't support py312"
    )
    def testConvergenceHEBO(self):
        from ray.tune.search.hebo import HEBOSearch

        np.random.seed(0)
        searcher = HEBOSearch()
        analysis = self._testConvergence(searcher)

        assert len(analysis.trials) < 100
        assert math.isclose(analysis.best_config["x"], 0, abs_tol=1e-2)

    def testConvergenceHyperopt(self):
        from ray.tune.search.hyperopt import HyperOptSearch

        np.random.seed(0)
        searcher = HyperOptSearch(random_state_seed=1234)
        analysis = self._testConvergence(searcher, patience=50, top=5)

        assert math.isclose(analysis.best_config["x"], 0, abs_tol=1e-2)

    def testConvergenceNevergrad(self):
        import nevergrad as ng

        from ray.tune.search.nevergrad import NevergradSearch

        np.random.seed(0)
        searcher = NevergradSearch(optimizer=ng.optimizers.PSO)
        analysis = self._testConvergence(searcher, patience=50, top=5)

        assert math.isclose(analysis.best_config["x"], 0, abs_tol=1e-3)

    def testConvergenceOptuna(self):
        from ray.tune.search.optuna import OptunaSearch

        np.random.seed(1)
        searcher = OptunaSearch(seed=1)
        analysis = self._testConvergence(
            searcher,
            top=5,
        )

        # This assertion is much weaker than in the BO case, but TPE
        # don't converge too close. It is still unlikely to get to this
        # tolerance with random search (5 * 0.1 = 0.5% chance)
        assert len(analysis.trials) < 100
        assert math.isclose(analysis.best_config["x"], 0, abs_tol=1e-1)

    def testConvergenceZoopt(self):
        from ray.tune.search.zoopt import ZOOptSearch

        np.random.seed(0)
        searcher = ZOOptSearch(budget=100)
        analysis = self._testConvergence(searcher)

        assert len(analysis.trials) < 100
        assert math.isclose(analysis.best_config["x"], 0, abs_tol=1e-3)


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))
