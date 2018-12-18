const { handler } = require(".");

const interval = (parseInt(process.env["INTERVAL"]) || 3600) * 1000;

setInterval(() => {
  handler()
    .then(result => {
      console.info(`${new Date().toISOString()}:`, result);
    })
    .catch(error => {
      console.error(`${new Date().toISOString()}:`, error);
    });
}, interval);
