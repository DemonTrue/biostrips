import os
import cyt_chart as cyt
import shutil


def generate_charts(dir_name, path_data, colormap, cyt_potential):
    # colormap = 'linear' or 'percentile'
    formats = ['png', 'svg', 'pdf']
    path_formats = []

    reactions = cyt.read_data(path_data)
    all_cyt_metrics = {}

    cell_name = reactions[0][0]

    path_results = os.path.join('results', dir_name)

    for el in formats:
        path_formats.append(os.path.join(path_results, el))

    try:
        os.mkdir(path_results)
        for el in path_formats:
            try:
                os.mkdir(el)
            except OSError:
                pass
    except OSError:
        pass

    colors, cytotoxity_scale = cyt.choice_colormap(colormap, reactions)

    # scaling factor calculation
    scale_coef = cyt.calc_scaling_coef(reactions)

    # plotting a color map
    cyt.cyt_colormap(cytotoxity_scale, colors, cell_name, colormap, path_formats, formats)

    # cycle through reactions from a file
    for count, reaction in enumerate(reactions):
        if count == 0:
            continue
        else:
            path_graph = []
            full_data = reaction[0]
            reaction_name = reaction[1][0]
            cyt_metrics = cyt.calc_cyt_metrics(reaction[3], reaction[4])  # calculation of cytotoxicity metrics
            biofactor = cyt_metrics[0]
            all_cyt_metrics[reaction_name] = cyt_metrics

            for el in path_formats:
                path_graph.append(os.path.join(el, reaction_name))
            # creating an array of colors for the substances in the considered reaction
            colors_data = cyt.fill_colors(reaction[5], colors, cytotoxity_scale)
            # plotting a diagram for a given reaction
            cyt.cyt_chart(path_graph, full_data, reaction_name, reaction[2], reaction[3], reaction[4], biofactor, colors_data, formats, scale_coef)

    # writing a table with cytotoxicity metrics
    cyt_table_name = dir_name + '_cyt_metrics.csv'
    path_cyt_table = os.path.join(path_results, cyt_table_name)

    with open(path_cyt_table, "w", encoding="utf-8") as out_file:
        print('combinations,biofactor,CPi (initial CP),CPf (final CP),CPf_rel (relative final CP)', file=out_file)
        for el in all_cyt_metrics.items():
            print(el[0], end=',', file=out_file)

            len_cyt_numbers = len(el[1])
            for count, number in enumerate(el[1]):
                if count == len_cyt_numbers - 1:
                    print(number, end='\n', file=out_file)
                else:
                    print(number, end=',', file=out_file)


    # search for the best combinations by the specified metric
    metric = cyt_potential
    # top_size = 5
    if len(all_cyt_metrics) < 5:
        top_size = len(all_cyt_metrics)
    else:
        top_size = 5
    top_combinations = cyt.find_top_combinations(all_cyt_metrics, metric, top_size)

    path_png = os.path.join(path_results, 'png')
    path_static = os.path.join('static', 'figures', dir_name)

    if os.path.isdir(path_static):
        shutil.rmtree(path_static)

    shutil.copytree(path_png, path_static)

    # сopying a file with all combinations
    comb_table_name = dir_name + '_comb.txt'
    path_comb_table = os.path.join(path_results, comb_table_name)

    shutil.copyfile(path_data, path_comb_table)

    return top_combinations
