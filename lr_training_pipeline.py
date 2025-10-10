"""
Loan Fraud Detection Model (Behavioral + Financial Rules Only)
---------------------------------------------------------------
Detects inflated or bot-like loan applications.

Features used:
- Financial: loan_amount, tuition_amount, annual_income, cosigner_income
- Derived: loan_over_tuition, loan_to_income, excess_amount
- Behavioral analytics: typing_speed, avg_keypress_interval, hesitation_time, mouse_variance
- Device/Usage patterns: same_device_count, same_ip_count, num_apps_last_30_days
- Temporal: hour_of_day, is_night_submission
- Rule-based red flags: loan > 1.5x tuition, behavioral anomalies, etc.

Pipeline:
1. Train Logistic Regression for fraud classification
2. Train IsolationForest for anomaly detection
3. Combine rule_score + ML probability + anomaly likelihood → final_risk

Usage:
    python lr_training_pipeline.py --train data.csv --out_dir models
    python lr_training_pipeline.py --predict_sample sample.json
"""

import argparse
import os
import json
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import average_precision_score, classification_report
import joblib

# ----------------------------- #
# RULE SCORE BUILDER
# ----------------------------- #
def compute_rule_score(row: pd.Series) -> Tuple[float, Dict[str, float]]:
    weights = {}
    tuition = row.get('tuition_amount', 0.0)
    loan = row.get('loan_amount', 0.0)
    income = row.get('annual_income', 0.0)

    loan_over_tuition = row.get('loan_over_tuition', loan / tuition if tuition > 0 else 0.0)
    loan_to_income = row.get('loan_to_income', loan / income if income > 0 else 0.0)
    excess_amount = loan - tuition

    # Rule 1: Inflated loan
    if loan_over_tuition > 1.5:
        weights['loan_over_tuition_gt_1_5'] = 0.5
    elif 1.2 < loan_over_tuition <= 1.5:
        weights['loan_over_tuition_1_2_1_5'] = 0.25

    # Rule 2: Loan-to-income ratio high
    if loan_to_income > 1.5:
        weights['loan_to_income_gt_1_5'] = 0.3
    elif 0.8 <= loan_to_income <= 1.5:
        weights['loan_to_income_0_8_1_5'] = 0.15

    # Rule 3: Behavioral anomaly
    if row.get('typing_speed', 0) > 8 and row.get('avg_keypress_interval', 9999) < 50 and row.get('mouse_variance', 9999) < 0.2:
        weights['bot_like_behavior'] = 0.3

    # Rule 4: Large excess
    if excess_amount > 50000:
        weights['excess_amount_gt_50k'] = 0.2

    rule_score = np.clip(sum(weights.values()), 0, 1)
    return rule_score, weights

# ----------------------------- #
# FEATURE ENGINEERING
# ----------------------------- #
def engineer_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, list]:
    df = df.copy()

    # Convert columns to numeric safely
    numeric_cols = [
        'loan_amount', 'tuition_amount', 'annual_income', 'cosigner_income',
        'typing_speed', 'avg_keypress_interval', 'hesitation_time', 'mouse_variance',
        'same_device_count', 'same_ip_count', 'num_apps_last_30_days'
    ]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
        else:
            df[c] = 0.0  # default column of zeros

    # Derived ratios
    df['loan_over_tuition'] = df.apply(
        lambda r: (r['loan_amount'] / r['tuition_amount']) if r['tuition_amount'] > 0 else 0.0,
        axis=1
    )
    df['loan_to_income'] = df.apply(
        lambda r: (r['loan_amount'] / (r['annual_income'] + (r.get('cosigner_income', 0) or 0)))
        if (r['annual_income'] + (r.get('cosigner_income', 0) or 0)) > 0 else 0.0,
        axis=1
    )
    df['excess_amount'] = df['loan_amount'] - df['tuition_amount']
    df['flag_loan_gt_1_5x_tuition'] = (df['loan_over_tuition'] > 1.5).astype(int)

    # Time-based features
    if 'application_timestamp' in df.columns:
        df['application_timestamp'] = pd.to_datetime(df['application_timestamp'], errors='coerce')
        df['hour_of_day'] = df['application_timestamp'].dt.hour.fillna(0).astype(int)
        df['is_night_submission'] = ((df['hour_of_day'] <= 4) | (df['hour_of_day'] >= 23)).astype(int)
    else:
        df['hour_of_day'] = 12
        df['is_night_submission'] = 0

    # Log transforms
    for c in ['loan_amount', 'tuition_amount', 'excess_amount', 'mouse_variance']:
        df[f'log1p_{c}'] = np.log1p(df[c].clip(lower=0))

    # Compute rule score
    df['rule_score'], df['rule_details'] = 0.0, '{}'
    for i, row in df.iterrows():
        score, details = compute_rule_score(row)
        df.at[i, 'rule_score'] = score
        df.at[i, 'rule_details'] = json.dumps(details)

    feature_cols = [
        'loan_amount', 'tuition_amount', 'annual_income', 'cosigner_income',
        'loan_over_tuition', 'loan_to_income', 'excess_amount', 'flag_loan_gt_1_5x_tuition',
        'typing_speed', 'avg_keypress_interval', 'hesitation_time', 'mouse_variance',
        'same_device_count', 'same_ip_count', 'num_apps_last_30_days',
        'hour_of_day', 'is_night_submission', 'rule_score'
    ]

    # Replace any remaining inf/-inf
    df.replace([np.inf, -np.inf], 0.0, inplace=True)

    return df.fillna(0.0), feature_cols

# ----------------------------- #
# TRAINING
# ----------------------------- #
def train_pipeline(csv_path: str, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    df = pd.read_csv(csv_path)
    if 'is_fraud' not in df.columns:
        raise ValueError("Training data must contain 'is_fraud' column")

    df, features = engineer_features(df)
    X, y = df[features], df['is_fraud'].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(X, y, stratify=y, test_size=0.2, random_state=42)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    lr = LogisticRegression(max_iter=1500, class_weight='balanced', solver='saga')
    grid = GridSearchCV(lr, {'C': [0.1, 1.0, 10]}, scoring='average_precision', cv=3, n_jobs=-1)
    grid.fit(X_train_scaled, y_train)
    best_lr = grid.best_estimator_

    iso = IsolationForest(n_estimators=200, contamination=0.05, random_state=42)
    iso.fit(X_train_scaled[y_train == 0])

    y_prob = best_lr.predict_proba(X_test_scaled)[:, 1]
    iso_scores = iso.decision_function(X_test_scaled)
    anomaly = 1 - (iso_scores - iso_scores.min()) / (iso_scores.max() - iso_scores.min() + 1e-9)

    final_risk = 0.35 * X_test['rule_score'].values + 0.55 * y_prob + 0.1 * anomaly

    ap = average_precision_score(y_test, final_risk)
    print(f"Average Precision (AUPRC): {ap:.4f}")
    preds = (final_risk > 0.7).astype(int)
    print(classification_report(y_test, preds))

    # Save artifacts
    joblib.dump(scaler, os.path.join(out_dir, 'scaler.joblib'))
    joblib.dump(best_lr, os.path.join(out_dir, 'logistic_model.joblib'))
    joblib.dump(iso, os.path.join(out_dir, 'isolation_forest.joblib'))
    with open(os.path.join(out_dir, 'features.json'), 'w') as f:
        json.dump(features, f)
    print(f"✅ Models saved in {out_dir}")

# ----------------------------- #
# PREDICTION
# ----------------------------- #
def predict_single(app: Dict[str, Any], model_dir: str) -> Dict[str, Any]:
    scaler = joblib.load(os.path.join(model_dir, 'scaler.joblib'))
    lr_model = joblib.load(os.path.join(model_dir, 'logistic_model.joblib'))
    iso = joblib.load(os.path.join(model_dir, 'isolation_forest.joblib'))
    with open(os.path.join(model_dir, 'features.json')) as f:
        features = json.load(f)

    df = pd.DataFrame([app])
    df, features_local = engineer_features(df)
    X = df[features]
    X_scaled = scaler.transform(X)

    lr_prob = float(lr_model.predict_proba(X_scaled)[:, 1][0])
    iso_score = float(iso.decision_function(X_scaled)[0])
    anomaly_likelihood = float(1.0 - (1.0 / (1.0 + np.exp(-iso_score))))
    rule_score = float(df['rule_score'].iloc[0])

    final_risk = float(np.clip(0.35 * rule_score + 0.55 * lr_prob + 0.1 * anomaly_likelihood, 0, 1))

    return {
        'lr_prob': lr_prob,
        'anomaly_likelihood': anomaly_likelihood,
        'rule_score': rule_score,
        'final_risk': final_risk,
        'rule_details': json.loads(df['rule_details'].iloc[0])
    }

# ----------------------------- #
# CLI
# ----------------------------- #
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--train', type=str)
    parser.add_argument('--out_dir', type=str, default='models')
    parser.add_argument('--predict_sample', type=str)
    args = parser.parse_args()

    if args.train:
        train_pipeline(args.train, args.out_dir)
    elif args.predict_sample:
        with open(args.predict_sample) as f:
            app = json.load(f)
        res = predict_single(app, args.out_dir)
        print(json.dumps(res, indent=2))
    else:
        print("Usage:\n--train data.csv --out_dir models\n--predict_sample sample.json")
