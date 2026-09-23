const form = document.querySelector('#evaluate-form');
const button = document.querySelector('#run-button');
const message = document.querySelector('#form-message');
const result = document.querySelector('#result');

const formatNumber = value => typeof value === 'number' ? value.toLocaleString('en-US') : value;

function showError(text) {
  message.textContent = text;
  message.style.color = '#b23a48';
  result.hidden = true;
}

function render(data) {
  result.hidden = false;
  document.querySelector('#result-seed').textContent = data.seed;
  document.querySelector('#environment').textContent = data.environment;
  const labels = { net_gain: 'Net gain', total_cost: 'Cost', total_contacts: 'Contacts', pilot_count: 'Pilots', final_campaign_count: 'Final campaigns' };
  document.querySelector('#metrics').innerHTML = Object.entries(labels).map(([key, label]) => `<div class="metric"><div class="metric-label">${label}</div><div class="metric-value">${formatNumber(data.metrics[key])}</div></div>`).join('');
  document.querySelector('#campaign-count').textContent = `${data.campaigns.length} campaigns`;
  document.querySelector('#campaigns').innerHTML = data.campaigns.map(campaign => `<article class="campaign"><strong>${campaign.campaign_name || 'Campaign'}</strong><div class="campaign-meta">${campaign.target_tariff} via ${campaign.channel}<br>${campaign.filter_arpu_segment || 'ALL'} / ${campaign.filter_current_tariff || 'ALL'}</div></article>`).join('');
  const warnings = document.querySelector('#warnings');
  warnings.hidden = !data.warnings.length;
  warnings.textContent = data.warnings.join(' ');
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  button.disabled = true;
  message.textContent = 'Running evaluation...';
  message.style.color = '';
  try {
    const response = await fetch('/api/evaluate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ seed: Number(document.querySelector('#seed').value) }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error?.message || 'Evaluation failed');
    render(data);
    message.textContent = `Completed in ${data.duration_seconds}s`;
  } catch (error) { showError(error.message); } finally { button.disabled = false; }
});