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

function diff(a, b, compare) {
  const add = [];
  const remove = [];

  const aIndex = new Set(a.map(compare));
  const bIndex = new Set(b.map(compare));

  for (const n of a) {
    if (!bIndex.has(compare(n))) {
      add.push(n);
    }
  }

  for (const n of b) {
    if (!aIndex.has(compare(n))) {
      remove.push(n);
    }
  }

  return { add, remove };
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

async function traktGet(path) {
  const response = await fetch(`https://api.trakt.tv${path}`, {
    headers: {
      Authorization: `Bearer ${process.env.TRAKT_ACCESS_TOKEN}`,
      "Content-Type": "application/json",
      "trakt-api-version": "2",
      "trakt-api-key": process.env.TRAKT_CLIENT_ID
    }
  });
  return await response.json();
}

async function traktPost(path, data) {
  const response = await fetch(`https://api.trakt.tv${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${process.env.TRAKT_ACCESS_TOKEN}`,
      "Content-Type": "application/json",
      "trakt-api-key": process.env.TRAKT_CLIENT_ID,
      "trakt-api-version": "2"
    },
    body: JSON.stringify(data)
  });
  return await response.json();
}

async function traktWatchlist() {
  const movies = await traktGet("/sync/watchlist/movies");
  return movies.map(movie => ({ id: movie.movie.ids.imdb })).filter(isImdb);
}

async function traktRatings() {
  const movies = await traktGet("/sync/ratings/movies");
  return movies
    .map(movie => ({ id: movie.movie.ids.imdb, rating: movie.rating }))
    .filter(isImdb);
}

async function traktWatched() {
  const movies = await traktGet("/sync/watched/movies");
  return movies.map(movie => ({ id: movie.movie.ids.imdb })).filter(isImdb);
}

function traktAdd(movies) {
  if (!movies.length) return {};
  return traktPost("/sync/watchlist", {
    movies: movies.map(movie => ({ ids: { imdb: movie.id } }))
  });
}

function traktRemove(movies) {
  if (!movies.length) return {};
  return traktPost("/sync/watchlist/remove", {
    movies: movies.map(movie => ({ ids: { imdb: movie.id } }))
  });
}

function traktRate(movies) {
  if (!movies.length) return {};
  return traktPost("/sync/ratings", {
    movies: movies.map(movie => ({
      rating: movie.rating,
      ids: { imdb: movie.id }
    }))
  });
}

function traktUnrate(movies) {
  if (!movies.length) return {};
  return traktPost("/sync/ratings/remove", {
    movies: movies.map(movie => ({
      ids: { imdb: movie.id }
    }))
  });
}

function traktWatch(movies) {
  if (!movies.length) return {};
  return traktPost("/sync/history", {
    movies: movies.map(movie => ({
      watched_at: movies.timestamp,
      ids: { imdb: movie.id }
    }))
  });
}

function traktUnwatch(movies) {
  if (!movies.length) return {};
  return traktPost("/sync/history/remove", {
    movies: movies.map(movie => ({
      ids: { imdb: movie.id }
    }))
  });
}

async function syncWatchlist() {
  const imdbWatchlistPromise = imdbWatchlist();
  const traktWatchlistPromise = traktWatchlist();
  const { add, remove } = diff(
    await imdbWatchlistPromise,
    await traktWatchlistPromise,
    movie => movie.id
  );
  return await Promise.all([traktAdd(add), traktRemove(remove)]);
}

async function syncRatings() {
  const imdbRatingsPromise = imdbRatings();
  const traktRatingsPromise = traktRatings();
  const { add, remove } = diff(
    await imdbRatingsPromise,
    await traktRatingsPromise,
    movie => movie.id
  );
  return await Promise.all([
    traktRate(add),
    traktWatch(add),
    traktUnrate(remove),
    traktUnwatch(remove)
  ]);
}

async function sync() {
  const syncWatchlistPromise = syncWatchlist();
  const syncRatingsPromise = syncRatings();
  return summary(await syncWatchlistPromise, await syncRatingsPromise);
}

function changeSummary(result) {
  const summary = [];

  for (const key in result) {
    const changes = result[key];
    const message = [];
    for (const key in changes) {
      const change = changes[key];
      if (typeof change === "number") {
        if (change > 0) message.push(`${change} ${key}`);
      } else if (typeof change === "object") {
        if (change.length > 0) message.push(JSON.stringify(change));
      }
    }

    if (message.length) summary.push(`${key}: ${message.join(", ")}`);
  }

  return summary.length > 0 ? summary.join(", ") : "no change";
}

function summary(watchlist, ratings) {
  try {
    const [watchlistAdded, watchListDeleted] = watchlist;
    const [ratingsRate, ratingsWatch, ratingsUnrate, ratingsUnwatch] = ratings;

    return [
      `watchlist.added: ${changeSummary(watchlistAdded)}`,
      `watchlist.deleted: ${changeSummary(watchListDeleted)}`,
      `ratings.rate: ${changeSummary(ratingsRate)}`,
      `ratings.unrate: ${changeSummary(ratingsUnrate)}`,
      `ratings.watch: ${changeSummary(ratingsWatch)}`,
      `ratings.unwatch: ${changeSummary(ratingsUnwatch)}`
    ].join("\n");
  } catch (error) {
    return `summary error: ${JSON.stringify(result)}`;
  }
}

exports.handler = () => {
  return sync();
};
