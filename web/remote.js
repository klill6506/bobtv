const statusLine = document.querySelector('#status');
let token = location.hash.slice(1);
try {
  if (token) localStorage.setItem('bobtv-remote-token', token);
  else token = localStorage.getItem('bobtv-remote-token') || '';
} catch (_) { /* The pairing link also works with storage disabled. */ }
// Keep the pairing fragment in bookmarks and iOS Home Screen shortcuts.
// URL fragments are never sent to the server.
let ready = false;
function disable(value) {
  document.querySelectorAll('button').forEach(button => { button.disabled = value; });
}
async function request(path, data) {
  const options = {headers: {'X-BobTV-Token': token}};
  if (data) {
    options.method = 'POST';
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(data);
  }
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || 'The TV could not complete that button.');
  return body;
}
async function send(data) {
  disable(true);
  statusLine.textContent = data.action === 'launch' ? 'Opening channel… the TV may need a moment to change region.' : 'Sending…';
  try { statusLine.textContent = (await request('/api/action', data)).message; }
  catch (error) { statusLine.textContent = error.message === 'Failed to fetch' ? 'Cannot reach BobTV. Check Wi-Fi and reload.' : error.message; }
  finally { disable(!ready); }
}
document.querySelectorAll('[data-action]').forEach(button => {
  button.addEventListener('click', () => send({action: button.dataset.action}));
});
async function connect() {
  disable(true);
  try {
    const catalog = await request('/api/catalog');
    for (const [id, service] of Object.entries(catalog.services)) {
      const button = document.createElement('button');
      button.textContent = service.name;
      const region = document.createElement('small');
      region.textContent = service.region.toUpperCase();
      button.append(region);
      button.addEventListener('click', () => send({action: 'launch', service: id}));
      document.querySelector('#channels').append(button);
    }
    ready = true;
    statusLine.textContent = 'Connected to BobTV';
    disable(false);
  } catch (error) { statusLine.textContent = error.message; }
}
connect();
