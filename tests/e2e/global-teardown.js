module.exports = async () => {
  if (!process.__TEST_SERVER__) return;
  try {
    process.__TEST_SERVER__.kill('SIGTERM');
  } catch (err) {
    console.error('Failed to kill test server:', err.message);
  }
};
