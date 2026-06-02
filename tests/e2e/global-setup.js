const { spawn } = require('child_process');
const path = require('path');

module.exports = async () => {
  const PORT = process.env.PORT || 8765;
  const serverScript = path.join(__dirname, 'server.py');

  return new Promise((resolve, reject) => {
    let settled = false;
    let stdoutBuffer = '';

    const server = spawn('python', [serverScript], {
      stdio: 'pipe',
      env: { ...process.env, PORT: String(PORT) },
    });

    const timeout = setTimeout(() => {
      if (!settled) {
        settled = true;
        reject(new Error('Server startup timeout'));
      }
    }, 15000);

    function done(err, val) {
      if (!settled) {
        settled = true;
        clearTimeout(timeout);
        if (err) reject(err);
        else resolve(val);
      }
    }

    server.stdout.on('data', (data) => {
      stdoutBuffer += data.toString();
      const text = data.toString().trim();
      console.log(`[test-server] ${text}`);
      if (stdoutBuffer.includes('started')) {
        done(null);
      }
    });

    server.stderr.on('data', (data) => {
      const text = data.toString().trim();
      console.log(`[test-server] ${text}`);
      if (text.includes('ERROR') || text.includes('Traceback')) {
        done(new Error(text));
      }
    });

    server.on('error', (err) => {
      console.error('Failed to start test server:', err);
      done(err);
    });

    server.on('exit', (code) => {
      if (!settled) {
        done(new Error(`Server exited with code ${code}`));
      }
    });

    process.__TEST_SERVER__ = server;
  });
};
