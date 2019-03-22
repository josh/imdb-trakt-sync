const fetch = require("node-fetch");
const fs = require("fs");

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

async function syncWatchlist(imdbWatchlistFilename) {
  const imdbWatchlistPromise = JSON.parse(fs.readFileSync(imdbWatchlistFilename, "utf8"));
  const traktWatchlistPromise = traktWatchlist();
  const { add, remove } = diff(
    await imdbWatchlistPromise,
    await traktWatchlistPromise,
    movie => movie.id
  );
  return await Promise.all([traktAdd(add), traktRemove(remove)]);
}

async function syncRatings(imdbRatingsFilename) {
  const imdbRatingsPromise = JSON.parse(fs.readFileSync(imdbRatingsFilename, "utf8"));
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

(async function() {
  switch (process.argv[2]) {
    case "watchlist":
      console.log(await syncWatchlist(process.argv[3]));
      break;
    case "ratings":
      console.log(await syncRatings(process.argv[3]));
      break;
  }
})();
