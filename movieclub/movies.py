import os
import uuid

from textwrap import shorten

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for,
    current_app
)
from werkzeug.utils import secure_filename
from werkzeug.exceptions import abort

from movieclub.auth import login_required
from movieclub.db import get_db

bp = Blueprint('movies', __name__)


@bp.route('/')
def index():
    PER_PAGE = 8
    db = get_db()
    count = int(db.execute(
        'SELECT COUNT(id) FROM movie'
    ).fetchone()[0])

    pages = count // PER_PAGE + (count % PER_PAGE > 0)
    
    if request.args.get('p'):
        page = int(request.args.get('p'))
        if page > pages:
            abort(404)
        db = get_db()
        movies = db.execute(
            'SELECT id, title, synopsis, created, poster FROM movie'
            ' ORDER BY created DESC'
            ' LIMIT ? OFFSET ?',
            (PER_PAGE, (page-1) * PER_PAGE,)
        ).fetchall()
    else:
        db = get_db()
        movies = db.execute(
            'SELECT id, title, synopsis, created, poster FROM movie'
            ' ORDER BY created DESC'
            ' LIMIT ?',
            (PER_PAGE,)
        ).fetchall()

    return render_template('movies/index.html', movies=movies,
                            shorten=shorten, pages=pages)


def allowed_file(filename):
    return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in \
            current_app.config['ALLOWED_EXTENSIONS']


@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    if request.method == 'POST':
        unique_filename = None
        age_ratings = [
            'U',
            'PG',
            '12A',
            '15',
            '18',
        ]

        title = request.form['title']
        synopsis = request.form['synopsis']
        released = request.form['release_year']
        age_rating = request.form['age_rating']
        error = None

        if not title:
            error = 'Title is required.'
        elif not released:
            error = 'Release year is required.'
        elif not synopsis:
            error = 'Synopsis is required.'
        elif not age_rating or age_rating not in age_ratings:
            error = 'Age rating required.'

        if error is not None:
            flash(error)
        else:
            if 'poster' in request.files:
                poster = request.files['poster']
                if poster and allowed_file(poster.filename):
                    filename = secure_filename(poster.filename)
                    unique_filename = str(uuid.uuid4().hex) + '.' + filename.rsplit(".", 1)[1]
                    poster_path = os.path.join(
                        current_app.config['UPLOAD_FOLDER'], unique_filename
                    )
                    poster.save(poster_path)
            
            db = get_db()
            db.execute(
                'INSERT INTO movie (title, synopsis, released, age_rating, user_id, poster)'
                ' VALUES (?, ?, ?, ?, ?, ?)',
                (title, synopsis, released, age_rating, g.user['id'], unique_filename)
            )
            db.commit()

            return redirect(url_for('movies.index'))

    return render_template('movies/create.html')


def get_movie(id):
    movie = get_db().execute(
        'SELECT id, title, synopsis, released, age_rating, poster'
        ' FROM movie WHERE id = ?',
        (id,)
    ).fetchone()

    if movie is None:
        abort(404, f"Movie id {id} doesn't exist.")

    return movie


@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    movie = get_movie(id)

    if request.method == 'POST':
        title = request.form['title']
        synopsis = request.form['synopsis']
        release_year = request.form['release_year']
        age_rating = request.form['age_rating']
        error = None

        if not title:
            error = 'Title is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'UPDATE movie SET title = ?, synopsis = ?, released = ?,'
                ' age_rating = ? WHERE id = ?',
                (title, synopsis, release_year, age_rating, id)
            )
            db.commit()
            return redirect(url_for('movies.index'))
    
    return render_template('movies/update.html', movie=movie)


def get_ratings(id):
    rating = None
    ratings = get_db().execute(
        'SELECT rating FROM rating WHERE movie_id = ?', (id,)
    ).fetchall()

    ratings = [rating['rating'] for rating in ratings]
    if len(ratings) > 0:
        rating = round(sum(ratings) / len(ratings), 1)

    return rating


def rate_movie(id):
    data = {'msg': None, 'error': None,}
    rating = int(request.form['rating'])

    # check user is logged in
    if g.user is not None:
        db = get_db()
        user_already_rated = db.execute(
            'SELECT * FROM rating WHERE user_id = ?'
            ' AND movie_id = ?',
            (g.user['id'], id,)
        ).fetchone() is not None

        if not rating or rating > 5:
            data['error'] = 'Please choose a rating from 1-5.'
        if user_already_rated:
            data['error'] = 'You have already rated this movie.'

        if data['error'] is None:
            db = get_db()
            db.execute(
                'INSERT INTO rating (rating, user_id, movie_id)'
                ' VALUES (?, ?, ?)',
                (rating, g.user['id'], id)
            )
            db.commit()
            data['msg'] = 'Thank you for your rating.'
            data['rating'] = get_ratings(id)
    else:
        data['error'] = 'Please login to rate this movie.'

    return data


@bp.route('/<int:id>', methods=('GET', 'POST'))
def view(id):
    movie = get_movie(id)
    rating = get_ratings(id)

    if request.method == 'POST':
        return rate_movie(id)

    return render_template('movies/view.html', movie=movie, rating=rating)
