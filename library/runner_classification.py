import json
import datetime
import h5py

import numpy as np
import torch
import torch.nn as nn

from .runner_common import FILES_LIST, SAMPLING_RATE, data_generator
from . import bench_models_regression


MAX_ITERATIONS_COUNT = 10_000
METRIC_ITERATIONS = 1_000

# MAX_ITERATIONS_COUNT = 5000
# METRIC_ITERATIONS = 100

TEST_START_FILE_INDEX = 5

def corr_multiple(x, y):
    assert x.shape[1] == y.shape[1]
    return [np.corrcoef(x[:, i],  y[:, i], rowvar=False)[0, 1] for i in range(x.shape[1])]


def process_batch(bench_model, generator, is_train, iteration):
    loss_function = nn.MSELoss()
    
    if is_train:
        bench_model.model.train()
    else:
        bench_model.model.eval()

    x_batch, y_batch = next(generator)

    y_batch_speech_indexes = bench_model.detect_voice(y_batch)

    assert x_batch.shape[0] == y_batch.shape[0]
    x_batch = torch.FloatTensor(x_batch).cuda()
    y_batch = torch.FloatTensor(y_batch).cuda()

    if is_train:
        bench_model.optimizer.zero_grad()

    y_predicted = bench_model.model(x_batch)
    assert not torch.any(torch.isnan(y_predicted))

    loss = loss_function(y_predicted, y_batch)

    if is_train:
        loss.backward()
        bench_model.optimizer.step()

    assert y_predicted.shape[0] == y_batch.shape[0], f"{y_predicted.shape[0]} != {y_batch.shape[0]}"
    assert y_predicted.shape[1] == y_batch.shape[1], f"{y_predicted.shape[1]} != {y_batch.shape[1]}"

    metrics = {}

    y_predicted_numpy = y_predicted.cpu().detach().numpy()
    y_batch_numpy = y_batch.cpu().detach().numpy()

    metrics["loss"] = float(loss.cpu().detach().numpy())

    metrics["correlation"] = float(np.nanmean(corr_multiple(y_predicted_numpy, y_batch_numpy)))

    if np.any(y_batch_speech_indexes):
        metrics["correlation_speech"] = float(np.nanmean(corr_multiple(y_predicted_numpy[y_batch_speech_indexes], y_batch_numpy[y_batch_speech_indexes])))

    for key, value in metrics.items():
        bench_model.logger.add_value(key, is_train, value, iteration)

    return metrics


def get_random_predictions(model, generator, iterations):
    Y_batch = []
    Y_predicted = []
    for index, (x_batch, y_batch) in enumerate(generator):
        x_batch = torch.FloatTensor(x_batch).cuda()
        y_predicted = model(x_batch).cpu().detach().numpy()
        assert x_batch.shape[0]==y_predicted.shape[0]
        Y_predicted.append(y_predicted)
        Y_batch.append(y_batch)
        if index > iterations:
            break

    Y_predicted = np.concatenate(Y_predicted, axis=0)
    Y_batch = np.concatenate(Y_batch, axis=0)
    return Y_batch, Y_predicted


def run_classification(bench_model_name, runs_count=1):
    assert hasattr(bench_models_regression, bench_model_name)
    bench_model = getattr(bench_models_regression, bench_model_name)()

    X = []
    Y = []

    for filepath in FILES_LIST:
        with h5py.File(filepath,'r+') as input_file:
            data = input_file['RawData']['Samples'][()]

        ecog = data[:, :30].astype("double")
        sound = data[:, 31].astype("double")

        x = bench_model.preprocess_ecog(ecog, SAMPLING_RATE).astype("float32")
        y = bench_model.preprocess_sound(sound, SAMPLING_RATE, x.shape[0]).astype("float32")

        if len(y.shape) == 1:
            y = y.reshape((-1, 1))

        assert x.shape[0] == y.shape[0]

        X.append(x)
        Y.append(y)
        
    X_train = np.concatenate(X[:TEST_START_FILE_INDEX], axis=0)
    Y_train = np.concatenate(Y[:TEST_START_FILE_INDEX], axis=0)
 
    X_val = np.concatenate(X[TEST_START_FILE_INDEX:], axis=0)
    Y_val = np.concatenate(Y[TEST_START_FILE_INDEX:], axis=0)
    
    X_test = np.concatenate(X[TEST_START_FILE_INDEX:], axis=0)
    Y_test = np.concatenate(Y[TEST_START_FILE_INDEX:], axis=0)

    batch_size = bench_model.BATCH_SIZE
    lag_backward = bench_model.LAG_BACKWARD
    lag_forward = bench_model.LAG_FORWARD

    train_generator = data_generator(X_train, Y_train, batch_size, lag_backward, lag_forward, shuffle=True, infinite=True)
    val_generator = data_generator(X_val, Y_val, batch_size, lag_backward, lag_forward, shuffle=True, infinite=True)

    for run_iteration in range(runs_count + 1):
        print("Run iteration:", run_iteration)
        max_metric = -float("inf")
        bench_model = getattr(bench_models_regression, bench_model_name)()
        model_filename = f"regression_{bench_model.__class__.__name__}_{str(datetime.datetime.now())}"
        model_path =  f"model_dumps/{model_filename}.pth"
        for iteration in range(MAX_ITERATIONS_COUNT):
            process_batch(bench_model, train_generator, True, iteration)
            with torch.no_grad():
                metrics = process_batch(bench_model, val_generator, False, iteration)
                is_last_iteration = iteration == (MAX_ITERATIONS_COUNT - 1)
                if (iteration % 2000 == 0 or is_last_iteration) and max_metric <= metrics["correlation"]:
                    max_metric = metrics["correlation"]
                    torch.save(bench_model.model.state_dict(), model_path)

        bench_model.model.load_state_dict(torch.load(model_path))
        bench_model.model.eval()

        test_generator = data_generator(X_test, Y_test, batch_size, lag_backward, lag_forward, shuffle=True, infinite=True)

        result = {}
        result["train_corr"] = np.mean(corr_multiple(*get_random_predictions(bench_model.model, train_generator, METRIC_ITERATIONS)))
        result["val_corr"] = np.mean(corr_multiple(*get_random_predictions(bench_model.model, val_generator, METRIC_ITERATIONS)))
        result["test_corr"] = np.mean(corr_multiple(*get_random_predictions(bench_model.model, test_generator, METRIC_ITERATIONS)))
        result["train_logs"] = bench_model.logger.train_logs
        result["val_logs"] = bench_model.logger.test_logs
        result["iterations"] = MAX_ITERATIONS_COUNT

        with open(f'results/{model_filename}.json', 'w') as result_file:
            json.dump(result, result_file)
                