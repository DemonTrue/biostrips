# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, flash, redirect, url_for, send_from_directory, session, app
from werkzeug.utils import secure_filename
from zipfile import ZipFile
import os
import generate_chart as gench
import generate_combinations_table as gentab
import input_validation as inpval
from flask_wtf import FlaskForm
from wtforms import StringField, FormField, FieldList, SelectField, Form, DecimalField
from wtforms.validators import DataRequired, NumberRange
from flask_bootstrap import Bootstrap
import logging
from logging.handlers import RotatingFileHandler
import json
from decimal import Decimal
from datetime import timedelta
from apscheduler.schedulers.gevent import GeventScheduler
import shutil


path_data = 'data'
path_meta = 'metadata'
path_results = 'results'
path_examples = 'examples'
path_new_chart_json = os.path.join(path_meta, 'new_chart.json')
path_figures = os.path.join('static', 'figures')
ALLOWED_EXTENSIONS = ['txt', 'csv']

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = path_data

bootstrap = Bootstrap(app)

with open(os.path.join(path_meta, 'secret_key.txt'), 'r') as f:
    app.config['SECRET_KEY'] = f.read()

menu = [{"name": "Main", "url": "/"},
        {"name": "Intro to bio-Strips", "url": '/intro_to_biostrips'},
        {"name": "Build Charts", "url": "/create-chart"},
        {"name": "Manual", "url": "/manual"},
        {"name": "About", "url": "/about"}]

colormap_list = [{'name': 'percentile'},
                 {'name': 'linear'}]

cyt_potentials_list = [{'name': 'BF'},
                       {'name': 'CPi'},
                       {'name': 'CPf'},
                       {'name': 'CPf_rel'}]


colormap_choices = [(el["name"], el["name"]) for el in colormap_list]
cyt_potential_choices = [(el["name"], el["name"]) for el in cyt_potentials_list]


class ReagentLineForm(Form):
    reagent_name = StringField("Reagent name: ", validators=[DataRequired()], description="Reagent name")
    reagent_role = StringField("Reagent role: ", validators=[DataRequired()], description="Reagent role")
    molar_mass = DecimalField("Molar mass: ", places=3,
                              validators=[DataRequired(), NumberRange(0.001)],
                              description="Molar mass")
    mass = DecimalField("Mass: ", places=10,
                       validators=[DataRequired(), NumberRange(0.0000000001)],
                       description="Mass")
    cc50 = DecimalField("CC50: ", places=10,
                       validators=[DataRequired(), NumberRange(0.0000000001)],
                       description="CC50")


class OneChartForm(FlaskForm):
    filename = StringField("Enter filename: ", validators=[DataRequired()], description="Filename")
    cell_name = StringField("Enter cell name: ", validators=[DataRequired()], description="Cell name")
    reagents_info = FieldList(FormField(ReagentLineForm), min_entries=1)
    products_info = FieldList(FormField(ReagentLineForm), min_entries=1)
    colormap = SelectField("Choose colormap: ")
    cyt_potential = SelectField("Choose cytotoxic potential: ")
    variables = StringField("Enter variables separated by commas: ", description="Variables")
    products_variables = StringField("Enter product variables separated by commas: ", description="Products variables")


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=30)


@app.route('/')
@app.route('/home')
def main():
    path_references = os.path.join(path_meta, 'references.txt')
    try:
        with open(path_references, 'r') as file:
            references = [line.replace('\n', '') for line in file.readlines()]
    except:
        references = ''

    return render_template('main.html', menu=menu, references=references)


@app.route('/manual')
def manual():
    return render_template('manual.html', menu=menu)

@app.route('/intro_to_biostrips')
def intro_to_biostrips():
    path_references = os.path.join(path_meta, 'references.txt')
    try:
        with open(path_references, 'r') as file:
            references = [line.replace('\n', '') for line in file.readlines()]
    except:
        references = ''

    return render_template('introduction-to-biostrips.html', menu=menu, references=references)


@app.route('/create-chart', methods=['POST', 'GET'])
def create_chart():
    form = OneChartForm()
    form.colormap.choices = colormap_choices
    form.cyt_potential.choices = cyt_potential_choices

    if 'send_create' in request.form:
        filename = form.filename.data
        cell_name = form.cell_name.data
        colormap = form.colormap.data
        cyt_potential = form.cyt_potential.data
        reagents_info = form.reagents_info.data
        products_info = form.products_info.data
        variables = form.variables.data
        products_variables = form.products_variables.data

        save_chart_data(filename, cell_name, reagents_info, products_info, variables, products_variables)
        form_data = json.dumps(form.data, cls=DecimalEncoder)

        session["OneChartForm"] = form_data
        session["filename"] = filename + '.txt'
        session["colormap"] = colormap
        session["cyt_potential"] = cyt_potential
        session["variables"] = variables
        session["product_variables"] = products_variables
        session["data_upload"] = 1
        session["form_chart"] = 1

    elif "data_upload" in session:
        if 'send_upload' in request.form:
            session["data_upload"] = 1
            session["form_chart"] = 0

    else:
        if request.method == 'GET':
            session["data_upload"] = 0
            session["graphs"] = []
            session["form_chart"] = 0


    if session["data_upload"] == 1:
        file_info = {'title': session["filename"], 'colormap': session["colormap"], 'cyt_potential': session["cyt_potential"]}
        filename = file_info['title']

        if 'gencombs' in request.form:
            message = data_validation(file_info)

            if message == 'SUCCESS':
                filename = session["filename"]
                path_table, number_of_combinations = calc_combinations(file_info)
                session["path_table"] = path_table
                session["number_of_combinations"] = number_of_combinations
                session["combs_found"] = 1

            else:
                flash(message)

            form_chart = session["form_chart"]

            if form_chart == 1:
                form_data = session.get("OneChartForm")

                form = OneChartForm()
                form.colormap.choices = colormap_choices
                form.cyt_potential.choices = cyt_potential_choices

                form.process(data=json.loads(form_data))

        if 'gencharts' in request.form:
            path_table = session["path_table"]

            top_combinations = make_chart(file_info, path_table)
            graphs = display_chart(filename)

            session["graphs"] = graphs
            session["charts_built"] = 1
            session["combs_found"] = 1
            session["top_combinations"] = top_combinations

            form_chart = session["form_chart"]

            if form_chart == 1:
                form_data = session.get("OneChartForm")

                form = OneChartForm()
                form.colormap.choices = colormap_choices
                form.cyt_potential.choices = cyt_potential_choices

                form.process(data=json.loads(form_data))

    else:
        file_info = {'title': 'NONE', 'colormap': 'NONE', 'cyt_potential': 'NONE'}
        reset_session()

    return render_template('create-chart.html', menu=menu, colormap_list=colormap_list,
                           cyt_potentials_list=cyt_potentials_list, json=file_info, session=session, form=form)


@app.route('/save_chart_data')
def save_chart_data(filename, cell_name, reagents_info, products_info, variables, products_variables):
    path_file = os.path.join(path_data, filename + '.txt')

    with open(path_file, "w", encoding='utf-8') as out_file:
        print("Cell", cell_name, sep='\t', end='\n', file=out_file)
        print("Variables", variables, sep='\t', end='\n', file=out_file)
        print("Product variables", products_variables, sep='\t', end='\n', file=out_file)
        print("Samples", "Abbreviation", "Mr, g*mol-1", "Mass, g", "CC50, mM", sep='\t', end='\n', file=out_file)
        print("Starting materials", end='\n', file=out_file)

        for el in reagents_info:
            print(el["reagent_name"], end='\t', file=out_file)
            print(el["reagent_role"], end='\t', file=out_file)
            print(el["molar_mass"], end='\t', file=out_file)
            print(el["mass"], end='\t', file=out_file)
            print(el["cc50"], end='\n', file=out_file)

        print("Products", end='\n', file=out_file)

        for el in products_info:
            print(el["reagent_name"], end='\t', file=out_file)
            print(el["reagent_role"], end='\t', file=out_file)
            print(el["molar_mass"], end='\t', file=out_file)
            print(el["mass"], end='\t', file=out_file)
            print(el["cc50"], end='\n', file=out_file)

    return 0


@app.route('/data_validation')
def data_validation(metadata):
    filename = metadata['title']
    path_file = os.path.join('data', filename)

    message = inpval.data_validation(path_file)

    return message


@app.route('/calc_combinations')
def calc_combinations(metadata):
    filename = metadata['title']
    path_file = os.path.join('data', filename)

    path_table, number_of_combinations = gentab.generate_table(path_file)

    return path_table, number_of_combinations


@app.route('/make_chart')
def make_chart(metadata, path_table):
    filename = metadata['title']
    colormap = metadata['colormap']
    cyt_potential = metadata['cyt_potential']
    dir_name = filename.rsplit('.', 1)[0]

    top_combinations = gench.generate_charts(dir_name, path_table, colormap, cyt_potential)

    return top_combinations


@app.route('/display_chart')
def display_chart(filename):
    dir_name = filename.rsplit('.', 1)[0]
    path_graphs = os.path.join(path_figures, dir_name)

    colormap_path = 'figures/' + dir_name + '/colormap.png'
    graphs = [colormap_path]

    for el in os.listdir(path_graphs):
        if el == 'colormap.png':
            continue
        else:
            graphs.append('figures/' + dir_name + '/' + el)

    return graphs


@app.route("/download/<path:filename>")
def download(filename):
    os.chdir(path_results)

    dir_name = filename.rsplit('.', 1)[0]
    zip_name = dir_name + '.zip'

    with ZipFile(zip_name, "w") as zip_arch:
        for dirpath, _, filenames in os.walk(dir_name):
            for filename in filenames:
                zip_arch.write(os.path.join(dirpath, filename))

    directory = os.path.join(app.root_path, path_results)
    reset_session()
    os.chdir('../')

    return send_from_directory(directory, zip_name)


@app.route("/reset_session")
def reset_session():
    session["data_upload"] = 0
    session["graphs"] = []
    session["filename"] = ''
    session["colormap"] = ''
    session["cyt_potential"] = ''
    session["combs_found"] = 0
    session["path_table"] = ''
    session["charts_built"] = 0
    session["top_combinations"] = ''
    session["number_of_combinations"] = 0
    session["OneChartForm"] = []
    session["form_chart"] = 0


@app.route("/download_file/<path:filename>", methods=['GET', 'POST'])
def download_file(filename):
    directory = os.path.join(app.root_path, path_examples)

    return send_from_directory(directory, filename, as_attachment=True)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/uploader', methods=['GET', 'POST'])
def uploader():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            colormap_name = request.form.get('colormap').replace('"', '')
            cyt_potential_name = request.form.get('cyt_potential').replace('"', '')

            session["filename"] = filename
            session["colormap"] = colormap_name
            session["cyt_potential"] = cyt_potential_name
            session["data_upload"] = 1
        else:
            extensions = 'Invalid file extension! The file must have one of the following extensions: '
            len_extensions = len(ALLOWED_EXTENSIONS)
            for count, extension in enumerate(ALLOWED_EXTENSIONS):
                if count == len_extensions - 1:
                    extensions += extension
                else:
                    extensions += extension + ','

            flash(extensions)

            return redirect(url_for('create_chart'))
    return redirect(url_for('create_chart'))


@app.errorhandler(404)
def pageNotFound(error):
    return render_template('page404.html', title="Страница не найдена", menu=menu), 404


@app.errorhandler(500)
def internal_error(exception):
    app.logger.error(exception)
    return render_template('internal-error.html', menu=menu), 500


def shedul_delete():
    with app.test_request_context():
        path_graphs = os.path.join('static', 'figures')
        delete_downloads(path_results)
        delete_downloads(path_data)
        delete_downloads(path_graphs)

        reset_session()


def delete_downloads(folder_path):
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))


scheduler = GeventScheduler()
scheduler.add_job(func=shedul_delete, trigger='interval', days=1)
scheduler.start()

if __name__ == '__main__':
    log_file = 'flask.log'

    file_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024 * 100, backupCount=20)
    file_handler.setLevel(logging.ERROR)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    app.logger.addHandler(file_handler)

    app.run(host="0.0.0.0")
