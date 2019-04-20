const fetch = require("node-fetch");
const fs = require("fs");

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
      rated_at: movie.timestamp,
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
      watched_at: movie.timestamp,
      ids: { imdb: movie.id }
    }))
  });
}

(async function() {
  const { add, remove } = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));

  switch (process.argv[2]) {
    case "watchlist":
      console.log(await Promise.all([traktAdd(add), traktRemove(remove)]));
      break;
    case "ratings":
      console.log(await Promise.all([traktRate(add), traktUnrate(remove)]));
      break;
    case "history":
      console.log(await Promise.all([traktWatch(add)]));
      break;
  }
})();
