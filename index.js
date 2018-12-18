const csv = require("csv");
const fetch = require("node-fetch");

function parseCSV(data) {
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

function imdbWatchlist() {
  return fetch(
    `http://www.imdb.com/list/${process.env.IMDB_WATCHLIST_ID}/export`,
    {
      headers: {
        Cookie: `id=${process.env.IMDB_SESSION_ID}`
      }
    }
  )
    .then(response => response.text())
    .then(text => parseCSV(text))
    .then(rows => rows.map(row => ({ id: row[1] })).filter(isImdb));
}

function imdbRatings() {
  return fetch(
    `http://www.imdb.com/user/${process.env.IMDB_RATINGS_ID}/ratings/export`,
    {
      headers: {
        Cookie: `id=${process.env.IMDB_ID}; sid=${process.env.IMDB_SID}`
      }
    }
  )
    .then(response => response.text())
    .then(text => parseCSV(text))
    .then(rows =>
      rows
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
        }))
    );
}

function traktGet(path) {
  return fetch(`https://api.trakt.tv${path}`, {
    headers: {
      Authorization: `Bearer ${process.env.TRAKT_ACCESS_TOKEN}`,
      "Content-Type": "application/json",
      "trakt-api-version": "2",
      "trakt-api-key": process.env.TRAKT_CLIENT_ID
    }
  }).then(response => response.json());
}

function traktPost(path, data) {
  return fetch(`https://api.trakt.tv${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${process.env.TRAKT_ACCESS_TOKEN}`,
      "Content-Type": "application/json",
      "trakt-api-key": process.env.TRAKT_CLIENT_ID,
      "trakt-api-version": "2"
    },
    body: JSON.stringify(data)
  }).then(response => response.json());
}

function traktWatchlist() {
  return traktGet("/sync/watchlist/movies").then(movies =>
    movies.map(movie => ({ id: movie.movie.ids.imdb })).filter(isImdb)
  );
}

function traktRatings() {
  return traktGet("/sync/ratings/movies").then(movies =>
    movies
      .map(movie => ({ id: movie.movie.ids.imdb, rating: movie.rating }))
      .filter(isImdb)
  );
}

function traktWatched() {
  return traktGet("/sync/watched/movies").then(movies =>
    movies.map(movie => ({ id: movie.movie.ids.imdb })).filter(isImdb)
  );
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

function syncWatchlist() {
  return Promise.all([imdbWatchlist(), traktWatchlist()]).then(
    ([imdbWatchlist, traktWatchlist]) => {
      const { add, remove } = diff(
        imdbWatchlist,
        traktWatchlist,
        movie => movie.id
      );
      return Promise.all([traktAdd(add), traktRemove(remove)]);
    }
  );
}

function syncRatings() {
  return Promise.all([imdbRatings(), traktRatings()]).then(
    ([imdbRatings, traktRatings]) => {
      const { add, remove } = diff(
        imdbRatings,
        traktRatings,
        movie => movie.id
      );
      return Promise.all([
        traktRate(add),
        traktWatch(add),
        traktUnrate(remove),
        traktUnwatch(remove)
      ]);
    }
  );
}

function sync() {
  return Promise.all([syncWatchlist(), syncRatings()]).then(summary);
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

function summary(result) {
  try {
    const [watchlist, ratings] = result;
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
