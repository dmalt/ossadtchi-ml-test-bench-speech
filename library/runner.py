from __future__ import annotations

import logging
from collections import deque
from typing import Any, Callable, Deque, Generator, Protocol

import numpy as np
import numpy.typing as npt
import torch
import torch.nn as nn
from torch.optim.optimizer import Optimizer
from torch.utils.data import DataLoader
from tqdm import trange  # type: ignore

from library.func_utils import infinite, log_execution_time
from library.type_aliases import ChanBatch, ChanBatchTensor, SigBatchTensor, SignalBatch

log = logging.getLogger(__name__)


def detect_voice(y_batch: SignalBatch, thresh: float = 1) -> npt.NDArray[np.bool_]:
    n_channels = y_batch.shape[1]
    return np.sum(y_batch > thresh, axis=1) > int(n_channels * 0.25)


def corr_multiple(x: SignalBatch, y: ChanBatch) -> list[Any]:
    assert x.shape[1] == y.shape[1], f"{x.shape=}, {y.shape=}"
    return [np.corrcoef(x[:, i], y[:, i], rowvar=False)[0, 1] for i in range(x.shape[1])]


def compute_regression_metrics(y_predicted: ChanBatch, y_true: ChanBatch) -> dict[str, float]:
    speech_idx = detect_voice(y_true)

    metrics = {}
    metrics["correlation"] = np.nanmean(corr_multiple(y_predicted, y_true))

    if speech_idx is not None:
        y_predicted, y_true = y_predicted[speech_idx], y_true[speech_idx]
        metrics["correlation_speech"] = float(np.nanmean(corr_multiple(y_predicted, y_true)))
    else:
        metrics["correlation_speech"] = 0

    return metrics


LossFunction = Callable[[ChanBatchTensor, ChanBatchTensor], torch.Tensor]


class TrainTestLoopRunner:
    def __init__(
        self,
        model: nn.Module,
        loader: DataLoader,
        optimizer: Optimizer | None = None,
        loss_function: LossFunction = nn.MSELoss(),
    ):
        self.model = model
        self.data_loader = loader
        self.optimizer = optimizer
        self.loss_function = loss_function

    def __iter__(self) -> Generator[tuple[ChanBatch, ChanBatch, float], None, None]:
        x_batch: SigBatchTensor
        y_batch: ChanBatchTensor
        for x_batch, y_batch in self.data_loader:
            if torch.cuda.is_available():
                x_batch, y_batch = x_batch.cuda(), y_batch.cuda()
            if self.optimizer is not None:
                y_predicted, loss = self.train_batch(x_batch, y_batch)
            else:
                y_predicted, loss = self.test_batch(x_batch, y_batch)
            yield y_predicted, y_batch.cpu().detach().numpy(), loss

    def train_batch(self, x: SigBatchTensor, y: ChanBatchTensor) -> tuple[ChanBatch, float]:
        self.model.train()
        assert self.optimizer is not None
        self.optimizer.zero_grad()
        y_predicted = self.model(x)
        loss = self.loss_function(y_predicted, y)
        loss.backward()
        self.optimizer.step()
        return y_predicted.cpu().detach().numpy(), float(loss.cpu().detach().numpy())

    def test_batch(self, x: SigBatchTensor, y: ChanBatchTensor) -> tuple[ChanBatch, float]:
        self.model.eval()
        with torch.no_grad():
            y_predicted = self.model(x)
            loss = self.loss_function(y_predicted, y)
        return y_predicted.cpu().detach().numpy(), float(loss.cpu().detach().numpy())


class ScalarTracker(Protocol):
    def add_scalar(self, tag: str, scalar_value: float, global_step: int | None) -> None:
        ...


MetricsComputer = Callable[[ChanBatch, ChanBatch], dict[str, float]]


@log_execution_time(desc="the experiment")
def run_experiment(
    model: nn.Module,
    optimizer: Optimizer,
    train_loader: DataLoader,
    test_loader: DataLoader,
    n_steps: int,
    upd_steps_freq: int,
    experiment_tracker: ScalarTracker,
    compute_metrics: MetricsComputer = compute_regression_metrics,
) -> None:

    model_filename = f"{model.__class__.__name__}"
    model_path = f"model_dumps/{model_filename}.pth"

    metrics_tracker = BestMetricsTracker()

    def to_metrics(args: tuple[ChanBatch, ChanBatch, float]) -> tuple[dict[str, float], float]:
        y_predicted, y_true, loss = args
        return compute_metrics(y_predicted, y_true), loss

    train_loop = map(to_metrics, infinite(TrainTestLoopRunner(model, train_loader, optimizer)))
    test_loop = map(to_metrics, infinite(TrainTestLoopRunner(model, test_loader)))
    tr = trange(n_steps, desc="Experiment main loop")
    for i, (m_train, l_train), (m_test, l_test) in zip(tr, train_loop, test_loop):
        for tag, value in m_train.items():
            experiment_tracker.add_scalar(f"ongoing_train/{tag}", value, i)
        experiment_tracker.add_scalar("ongoing_train/loss", l_train, i)
        for tag, value in m_test.items():
            experiment_tracker.add_scalar(f"ongoing_test/{tag}", value, i)
        experiment_tracker.add_scalar("ongoing_test/loss", l_test, i)

        metrics_tracker.update_buffer(np.array([v for v in m_test.values()]))
        if not i % upd_steps_freq and metrics_tracker.is_improved():
            metrics_tracker.update_best()
            log.info(f"Dumping model for iteration = {i}")
            torch.save(model.state_dict(), model_path)

    if metrics_tracker.is_improved():
        torch.save(model.state_dict(), model_path)

    model.load_state_dict(torch.load(model_path))  # type: ignore


class BestMetricsTracker:
    def __init__(self, metrics_buflen: int = 100):
        self.best_metrics: np.ndarray | None = None
        self.metrics_buffer: Deque[np.ndarray] = deque()
        self.buflen = metrics_buflen

    def update_buffer(self, new_metrics: np.ndarray) -> None:
        if len(self.metrics_buffer) >= self.buflen:
            self.metrics_buffer.popleft()
        self.metrics_buffer.append(new_metrics)

    def is_improved(self) -> bool:
        if self.best_metrics is None:
            return True
        smoothed_metrics = self.get_smoothed_metrics()
        return bool(np.all(smoothed_metrics >= self.best_metrics))

    def update_best(self) -> None:
        self.best_metrics = self.get_smoothed_metrics()

    def get_smoothed_metrics(self) -> np.ndarray:
        assert self.metrics_buffer, "buffer is empty"
        return np.asarray(self.metrics_buffer).mean(axis=0)