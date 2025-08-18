async function generateARN(userData, apiKey, apiSecret, maxRetries = 3) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch('https://buildwithhussain.com/api/v2/method/get_arn_number', {
        method: 'POST',
        headers: { 
          'Authorization': `token ${apiKey}:${apiSecret}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(userData)
      });

      if (response.ok) {
        const data = await response.json();
        const arn = data?.message?.arn_number || "Unknown";
        document.getElementById('result').textContent = `ARN: ${arn}`;
        return data;
      }

      if (response.status === 401) {
        throw new Error('Authentication failed - check API credentials');
      }

      throw new Error(`HTTP ${response.status}`);
    } catch (error) {
      console.log(`Attempt ${attempt} failed:`, error.message);
      if (attempt === maxRetries || error.message.includes('Authentication')) {
        document.getElementById('result').textContent = " Failed to generate ARN.";
        return;
      }
      await new Promise(resolve => setTimeout(resolve, 1000 * attempt)); 
    }
  }
}

function callARN(event) {
  event.preventDefault();

  const user_name = document.getElementById('user_name').value.trim();
  const invoice_number = document.getElementById('invoice_number').value.trim();

  if (!user_name || !invoice_number) {
    alert("Please enter both Username and Invoice Number.");
    return;
  }

  const userData = { user_name, invoice_number };
  const apiKey = "2c70587e2df4779";
  const apiSecret = "56331804ac8ca7b";

  generateARN(userData, apiKey, apiSecret);
}

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('arnForm');
  if (form) {
    form.addEventListener('submit', callARN);
  }
});
