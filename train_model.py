# train_model.py
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
import joblib

# -------------------------------
# Step 1: Load CSV dataset
# -------------------------------
df = pd.read_csv("loan_data.csv")  # Make sure CSV is in the same folder

# -------------------------------
# Step 2: Features and target
# -------------------------------
X = df[["age", "income", "loan_amount", "purpose"]]
y = df["fraud"]  # 0 = Legitimate, 1 = Fraud

# -------------------------------
# Step 3: Split dataset
# -------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# -------------------------------
# Step 4: Preprocessor
# -------------------------------
preprocessor = ColumnTransformer(
    transformers=[
        ("cat", OneHotEncoder(handle_unknown="ignore"), ["purpose"]),  # This line ensures unknown categories don't crash
        ("num", "passthrough", ["age", "income", "loan_amount"])
    ]
)

# -------------------------------
# Step 5: Pipeline
# -------------------------------
pipeline = Pipeline([
    ("preprocessor", preprocessor),
    ("classifier", LogisticRegression())
])

# -------------------------------
# Step 6: Train
# -------------------------------
pipeline.fit(X_train, y_train)

# -------------------------------
# Step 7: Test accuracy
# -------------------------------
accuracy = pipeline.score(X_test, y_test)
print(f"✅ Model trained! Test accuracy: {accuracy:.2f}")

# -------------------------------
# Step 8: Save model
# -------------------------------
joblib.dump(pipeline, "fraud_model.joblib")
print("✅ Model saved as 'fraud_model.joblib'")


