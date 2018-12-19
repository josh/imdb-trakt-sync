const { handler } = require(".");

const interval = (parseInt(process.env["INTERVAL"]) || 3600) * 1000;

setInterval(async () => {
  try {
    const result = await handler();
    console.info(`${new Date().toISOString()}:\n${result}`);
  } catch (error) {
    console.error(`${new Date().toISOString()}:`, error);
  }
}, interval);
