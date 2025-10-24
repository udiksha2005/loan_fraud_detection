/*const form = document.getElementById('applicationForm');
const resultSection = document.getElementById('result');

// Behavioral backtracking log
let behaviorLog = [];

// Track focus, blur, and input for all form fields
const formElements = document.querySelectorAll("#applicationForm input, #applicationForm select");

formElements.forEach(el => {
  // Focus event
  el.addEventListener("focus", (e) => {
    behaviorLog.push({
      field: e.target.id,
      action: "focus",
      time: new Date().toISOString()
    });
  });

  // Blur event
  el.addEventListener("blur", (e) => {
    behaviorLog.push({
      field: e.target.id,
      action: "blur",
      value: e.target.value,
      time: new Date().toISOString()
    });
  });

  // Input/change event
  el.addEventListener("input", (e) => {
    behaviorLog.push({
      field: e.target.id,
      action: "input",
      value: e.target.value,
      time: new Date().toISOString()
    });
  });
});

// Fraud score calculation
function calculateFraudScore(data) {
  let score = 0;
  const reasons = [];

  if(data.loan_amount > data.income * 5) { 
    score += 40; 
    reasons.push("Loan amount is very high compared to income"); 
  }
  if(data.income_proof === "No") { 
    score += 30; 
    reasons.push("No income proof provided"); 
  }
  if(data.age < 18) { 
    score += 20; 
    reasons.push("Applicant is under 18"); 
  }
  if(!data.college_id) { 
    score += 10; 
    reasons.push("College ID missing"); 
  }
  if(score > 100) score = 100;

  let status = "";
  if(score <= 30) status = "Approved";
  else if(score <= 70) status = "Pending";
  else status = "High Risk";

  return {score, status, reasons};
}

// Form submission
form.addEventListener('submit', function(e) {
  e.preventDefault();

  const formData = {
    name: document.getElementById('name').value,
    age: parseInt(document.getElementById('age').value),
    college: document.getElementById('college').value,
    college_id: document.getElementById('college_id').value,
    loan_amount: parseInt(document.getElementById('loan_amount').value),
    income: parseInt(document.getElementById('income').value),
    income_proof: document.getElementById('income_proof').value,
    email: document.getElementById('email').value,
    phone: document.getElementById('phone').value,
    purpose: document.getElementById('purpose').value
  };

  const result = calculateFraudScore(formData);

  // Display result
  resultSection.innerHTML = `
    <h2>Application Result</h2>
    <p><strong>Fraud Score:</strong> ${result.score}%</p>
    <p><strong>Status:</strong> ${result.status}</p>
    <p><strong>Reasons:</strong> ${result.reasons.join(", ") || "None"}</p>
  `;

  // Save to localStorage with behavioral log
  let applications = JSON.parse(localStorage.getItem('applications')) || [];
  applications.push({
    ...formData,
    fraud_score: result.score,
    status: result.status,
    reasons: result.reasons.join(", "),
    behaviorLog: behaviorLog
  });
  localStorage.setItem('applications', JSON.stringify(applications));

  // Reset form and behavior log
  form.reset();
  behaviorLog = [];
});
*/
const form = document.getElementById('applicationForm');
const resultSection = document.getElementById('result');

// Behavioral backtracking log
let behaviorLog = [];

// Track focus, blur, and input for all form fields
const formElements = document.querySelectorAll("#applicationForm input, #applicationForm select");

formElements.forEach(el => {
  // Focus event
  el.addEventListener("focus", (e) => {
    behaviorLog.push({
      field: e.target.id,
      action: "focus",
      time: new Date().toISOString()
    });
  });

  // Blur event
  el.addEventListener("blur", (e) => {
    behaviorLog.push({
      field: e.target.id,
      action: "blur",
      value: e.target.value,
      time: new Date().toISOString()
    });
  });

  // Input/change event
  el.addEventListener("input", (e) => {
    behaviorLog.push({
      field: e.target.id,
      action: "input",
      value: e.target.value,
      time: new Date().toISOString()
    });
  });
});

// Form submission
form.addEventListener('submit', async function(e) {
  e.preventDefault();

  const formData = {
    name: document.getElementById('name').value,
    age: parseInt(document.getElementById('age').value),
    college: document.getElementById('college').value,
    college_id: document.getElementById('college_id').value,
    loan_amount: parseInt(document.getElementById('loan_amount').value),
    income: parseInt(document.getElementById('income').value),
    income_proof: document.getElementById('income_proof').value,
    email: document.getElementById('email').value,
    phone: document.getElementById('phone').value,
    purpose: document.getElementById('purpose').value,
    
    // Optional behavioral features
    typing_speed: parseFloat(document.getElementById('typing_speed')?.value) || 0,
    avg_keypress_interval: parseFloat(document.getElementById('avg_keypress_interval')?.value) || 0,
    hesitation_time: parseFloat(document.getElementById('hesitation_time')?.value) || 0,
    mouse_variance: parseFloat(document.getElementById('mouse_variance')?.value) || 0
  };

  try {
    // Call backend API for fraud score
    const response = await fetch("http://localhost:8000/apply-loan-frontend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formData)
    });
    const result = await response.json();

    // Display result
    resultSection.innerHTML = `
      <h2>Application Result</h2>
      <p><strong>Fraud Score:</strong> ${result.fraud_score}%</p>
      <p><strong>Status:</strong> ${result.status}</p>
      <p><strong>Reasons:</strong> ${result.reasons.join(", ") || "None"}</p>
    `;

    // Save to localStorage with behavioral log
    let applications = JSON.parse(localStorage.getItem('applications')) || [];
    applications.push({
      ...formData,
      fraud_score: result.fraud_score,
      status: result.status,
      reasons: result.reasons.join(", "),
      behaviorLog: behaviorLog
    });
    localStorage.setItem('applications', JSON.stringify(applications));

    // Reset form and behavior log
    form.reset();
    behaviorLog = [];

  } catch (error) {
    console.error("Error submitting application:", error);
    alert("Something went wrong. Please try again later.");
  }
});
