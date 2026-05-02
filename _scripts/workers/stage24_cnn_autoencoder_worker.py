from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(os.environ.get("PROJECT3_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
sys.path.insert(0, str(ROOT / "_scripts" / "lib"))
sys.path.insert(0, str(ROOT / "_scripts" / "workers"))
from gpu_lock import acquire_gpu_lock, release_gpu_lock  # noqa: E402
from stage24_lstm_autoencoder_worker import configure_tensorflow, make_windows, read_matrix, rel  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(machine: str, message: str) -> None:
    path = ROOT / "_logs" / machine / "stage24_cnn_autoencoder_worker.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{utc_now()} {message}\n")


def batched_encode(encoder: Any, values: np.ndarray, timestamps: pd.Series, window: int, batch_size: int) -> pd.DataFrame:
    rows: list[np.ndarray] = []
    ts: list[pd.Timestamp] = []
    n = len(values) - window + 1
    for start in range(0, n, batch_size):
        count = min(batch_size, n - start)
        batch = np.empty((count, window, values.shape[1]), dtype=np.float32)
        for i in range(count):
            batch[i] = values[start + i : start + i + window]
            ts.append(timestamps.iloc[start + i + window - 1])
        rows.append(encoder.predict(batch, verbose=0))
    encoded = np.vstack(rows)
    out = pd.DataFrame(encoded, columns=[f"learned_cnn_{i:02d}" for i in range(encoded.shape[1])])
    out.insert(0, "timestamp", ts)
    return out


def run_job(
    machine: str,
    asset: str,
    timeframe: str,
    epochs: int,
    latent_dim: int,
    max_train_windows: int,
    batch_size: int,
) -> dict[str, Any]:
    window = 64 if timeframe in {"5m", "15m", "1h"} else 32
    out_dir = ROOT / "features" / "learned_models" / asset / timeframe / "cnn_autoencoder"
    out_dir.mkdir(parents=True, exist_ok=True)
    feature_out = ROOT / "features" / "trading_asset_features" / asset / timeframe / "learned_cnn.parquet"
    feature_out.parent.mkdir(parents=True, exist_ok=True)

    train = read_matrix(asset, timeframe, "train")
    val = read_matrix(asset, timeframe, "validation")
    full_path = ROOT / "features" / "learned_inputs" / asset / timeframe / "full_normalized.parquet"
    full = pd.read_parquet(full_path)
    full["timestamp"] = pd.to_datetime(full["timestamp"], utc=True, errors="coerce")
    cols = [col for col in train.columns if col != "timestamp"]
    x_train = make_windows(train[cols].to_numpy(dtype=np.float32), window, max_train_windows)
    x_val = make_windows(val[cols].to_numpy(dtype=np.float32), window, min(5000, max_train_windows // 4))

    tf = configure_tensorflow()
    inputs = tf.keras.Input(shape=(window, len(cols)), name="window")
    x = tf.keras.layers.Conv1D(64, 5, padding="same", activation="relu", name="encoder_conv1")(inputs)
    x = tf.keras.layers.BatchNormalization(name="encoder_bn1")(x)
    x = tf.keras.layers.MaxPooling1D(2, name="encoder_pool1")(x)
    x = tf.keras.layers.Conv1D(32, 3, padding="same", activation="relu", name="encoder_conv2")(x)
    x = tf.keras.layers.BatchNormalization(name="encoder_bn2")(x)
    x = tf.keras.layers.GlobalAveragePooling1D(name="encoder_pool_global")(x)
    latent = tf.keras.layers.Dense(latent_dim, name="latent")(x)
    x = tf.keras.layers.RepeatVector(window, name="decoder_repeat")(latent)
    x = tf.keras.layers.Conv1D(32, 3, padding="same", activation="relu", name="decoder_conv1")(x)
    x = tf.keras.layers.BatchNormalization(name="decoder_bn1")(x)
    x = tf.keras.layers.Conv1D(64, 5, padding="same", activation="relu", name="decoder_conv2")(x)
    outputs = tf.keras.layers.TimeDistributed(tf.keras.layers.Dense(len(cols)), name="reconstruction")(x)
    autoencoder = tf.keras.Model(inputs, outputs, name=f"{asset}_{timeframe}_cnn_autoencoder")
    encoder = tf.keras.Model(inputs, latent, name=f"{asset}_{timeframe}_cnn_encoder")
    autoencoder.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3), loss="mse")
    callbacks = [
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", patience=3, factor=0.5, min_lr=1e-5),
    ]
    history = autoencoder.fit(
        x_train,
        x_train,
        validation_data=(x_val, x_val),
        epochs=epochs,
        batch_size=batch_size,
        verbose=2,
        callbacks=callbacks,
    )
    autoencoder.save(out_dir / "autoencoder.keras")
    encoder.save(out_dir / "encoder.keras")
    encoded = batched_encode(
        encoder,
        full[cols].to_numpy(dtype=np.float32),
        full["timestamp"],
        window,
        batch_size=max(256, batch_size),
    )
    encoded.to_parquet(feature_out, index=False)
    metadata = {
        "generated_at": utc_now(),
        "stage": "Stage 2.4",
        "machine": machine,
        "asset": asset,
        "timeframe": timeframe,
        "method": "cnn_autoencoder",
        "window": window,
        "latent_dim": latent_dim,
        "input_columns": len(cols),
        "train_windows": int(len(x_train)),
        "validation_windows": int(len(x_val)),
        "epochs_requested": epochs,
        "epochs_completed": len(history.history.get("loss", [])),
        "final_loss": float(history.history["loss"][-1]),
        "final_val_loss": float(history.history["val_loss"][-1]),
        "encoder_path": rel(out_dir / "encoder.keras"),
        "autoencoder_path": rel(out_dir / "autoencoder.keras"),
        "features_path": rel(feature_out),
        "output_rows": int(len(encoded)),
        "note": "Bootstrap Stage 2.4 CNN autoencoder while feature-extractor runtime wrapper is being integrated.",
    }
    (out_dir / "training_summary.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", required=True)
    parser.add_argument("--asset", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--latent-dim", type=int, default=32)
    parser.add_argument("--max-train-windows", type=int, default=20_000)
    parser.add_argument("--batch-size", type=int, default=128)
    args = parser.parse_args()

    command = " ".join(sys.argv)
    log(args.machine, f"START stage24 cnn asset={args.asset} tf={args.timeframe}")
    acquire_gpu_lock(command=command, expected_duration_minutes=90, stage="2.4")
    try:
        summary = run_job(
            machine=args.machine,
            asset=args.asset,
            timeframe=args.timeframe,
            epochs=args.epochs,
            latent_dim=args.latent_dim,
            max_train_windows=args.max_train_windows,
            batch_size=args.batch_size,
        )
    finally:
        release_gpu_lock()
    report_path = ROOT / "_metadata" / f"stage24_cnn_autoencoder_{args.machine}_{args.asset}_{args.timeframe}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    log(args.machine, f"DONE stage24 cnn asset={args.asset} tf={args.timeframe} val_loss={summary['final_val_loss']:.6f}")


if __name__ == "__main__":
    main()
