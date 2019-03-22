const csv = require("csv");
const fetch = require("node-fetch");

async function parseCSV(data) {
  return new Promise((resolve, reject) => {
    csv.parse(data, (err, data) => {
      if (err) {
        reject(err);
      }
      resolve(data);
    });
  });
}

function isImdb(movie) {
  return movie.id.startsWith("tt");
}

async function imdbWatchlist() {
  const response = await fetch(
    `http://www.imdb.com/list/${process.env.IMDB_WATCHLIST_ID}/export`,
    {
      headers: {
        Cookie: `id=${process.env.IMDB_SESSION_ID}`
      }
    }
  );
  const text = await response.text();
  const rows = await parseCSV(text);
  return rows.map(row => ({ id: row[1] })).filter(isImdb);
}

(async function() {
  process.stdout.write(JSON.stringify(await imdbWatchlist()));
})();
