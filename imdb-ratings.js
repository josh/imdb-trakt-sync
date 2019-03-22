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

async function imdbRatings() {
  const response = await fetch(
    `http://www.imdb.com/user/${process.env.IMDB_RATINGS_ID}/ratings/export`,
    {
      headers: {
        Cookie: `id=${process.env.IMDB_ID}; sid=${process.env.IMDB_SID}`
      }
    }
  );
  const text = await response.text();
  const rows = await parseCSV(text);

  return rows
    .map(row => ({
      id: row[0],
      rating: row[1],
      timestamp: row[2]
    }))
    .filter(isImdb)
    .map(({ id, rating, timestamp }) => ({
      id,
      rating: parseInt(rating),
      timestamp: new Date(Date.parse(timestamp)).toISOString()
    }));
}

(async function() {
  process.stdout.write(JSON.stringify(await imdbRatings()));
})();
