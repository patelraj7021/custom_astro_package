# -*- coding: utf-8 -*-
"""
Created on Fri Feb 16 21:43:17 2024

@author: patel
"""

import time
import os
import random
from multiprocessing import Pool
import numpy as np
import pandas as pd
# from scikit-learn import train_test_split

# TensorFlow outputs unnecessary log messages
# GPU is working fine
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
from tensorflow.keras.callbacks import ModelCheckpoint
from tensorflow.keras.callbacks import EarlyStopping
import tensorflow as tf
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '0'



def split_GPU(num_splits, mem_each_split):
    # allow GPU memory to be fragmented so multiple models can be trained
    # at the same time
    
    config_input = []
    for i in range(num_splits):
        config_input.append(tf.config.LogicalDeviceConfiguration(
            memory_limit=mem_each_split))
    
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
      # Create 2 virtual GPUs with 1GB memory each
      try:
        tf.config.set_logical_device_configuration(
            gpus[0], config_input)
        logical_gpus = tf.config.list_logical_devices('GPU')
        #print(len(gpus), "Physical GPU,", len(logical_gpus), "Logical GPUs")
      except RuntimeError as e:
        # Virtual devices must be set before GPUs have been initialized
        print(e)
        
    return


def init_model_arch(lyrs, nodes, hidden_act, out_act, num_in_vars):
    
    # check inputs
    if type(lyrs) is not int or type(nodes) is not int \
        or type(num_in_vars) is not int: 
            raise TypeError(
            'Number of layers, nodes, and input variables must be integers.')
    if lyrs == 0 or nodes == 0 or num_in_vars == 0:
        raise ValueError(
        'Number of layers, nodes, and input variables must be greater than 0.')
    if type(hidden_act) is not str or type(out_act) is not str:
        raise TypeError(
        'Hidden and output layer activation names must be strings.')
    
    # run
    try:
        model_arch = Sequential()
        model_arch.add(Dense(nodes, input_shape=(num_in_vars,), 
                             activation=hidden_act))
        for i in range(lyrs-1):
            model_arch.add(Dense(nodes, activation=hidden_act))
        model_arch.add(Dense(1, activation=out_act))
    except ValueError:
        print(
        'Check keras documentation for valid activation and output functions.')
    return model_arch


def get_num_features(features_in):
    # get num. of features
    if len(features_in.shape) == 1:
        num_features = 1
    elif len(features_in.shape) > 2:
        raise TypeError('Rank of training data cannot be higher than two.')
    else:
        num_features = features_in.shape[1]
    return num_features


def train_model(features_in, target_vals, layers_num, eps,
                opt_alg='Nadam', loss_func='mse', batch_sz=64,
                vali_perc=0.3):
    
    # check inputs
    if type(vali_perc) is not float:
        raise TypeError('Validation percentage must be float.')
    if vali_perc > 1. or vali_perc == 0:
        raise ValueError('Validation data percentage must be >0 and <1.')
        
    num_features = get_num_features(features_in)
    
    NN_model = init_model_arch(layers_num, num_features+4,
                                 'relu', 'linear', num_features)
    
    # generate unique ID that won't exist already
    num_existing_models = len(os.listdir('model_saves'))
    rand_num = int(abs(7.*np.random.randn(1))*10000 - num_existing_models)
    rand_ID = str(rand_num) + str(num_existing_models)
    rand_ID = rand_ID.zfill(8)
    best_model_path = os.path.join('model_saves', 
                                   f'weights_{rand_ID}.hdf5')
    # save model with best val_loss, not the end state model
    save_best_model = ModelCheckpoint(best_model_path, monitor='val_loss', 
                                  save_best_only=True, save_weights_only=True)
    
    early_stopping = EarlyStopping(monitor='val_loss',
                                   patience=eps/10,
                                   mode='min',
                                   start_from_epoch=eps/10)
    
    NN_model.compile(loss=loss_func, optimizer=opt_alg)
    fitting_results = NN_model.fit(features_in, target_vals, 
                                 epochs=eps, batch_size=batch_sz,
                                 validation_split=vali_perc, verbose=0,
                                 callbacks=[save_best_model, early_stopping])
    
    # select the best model
    NN_model.load_weights(best_model_path)
    
    min_val_cost = round(min(fitting_results.history['val_loss']), 3)
    print(f'{layers_num}-layer model trained; min(val_cost) = {min_val_cost}')
          
    return fitting_results, NN_model


def exp_bag_weighted_avg(val_losses, predictions):
    # expects np arrays as input
    # val_losses: N by 1
    # predictions: len(rows of testing_X) by N
    # outputs np arrays
    # exp weighing makes neg. std dev predictions highly weighed (good preds.)
    # positive std dev predictions lowly weighed (bad preds.)
    # look at exp(-x) for intuition; normalizing centers val_losses at 0
    # implement maxes of -6 and +6 for normalized val_losses for stability
    
    val_losses_mean = np.mean(val_losses)
    val_losses_std = np.std(val_losses) 
    val_losses_norm = (val_losses - val_losses_mean) / val_losses_std
    val_losses_norm_clipped = np.clip(val_losses_norm, -6., 6.)
    weights = np.exp(-val_losses_norm_clipped)
    weighed_sum = np.dot(predictions, weights)
    weighed_average = weighed_sum / np.sum(weights)
    
    return weighed_average


def bag_models(features_in, target_vals, bag_quantity, layers_num, eps,
               testing_X, opt_alg='Nadam', loss_func='mse', batch_sz=64,
               vali_perc=0.3):
    
    predicted_bag = []
    min_val_loss_bag = []
    
    for i in range(bag_quantity):
        fitting_results, NN_model = train_model(features_in, target_vals,
                                                layers_num, eps, opt_alg, 
                                                loss_func, batch_sz, vali_perc)
        
        predicted_vals = NN_model.predict(testing_X)
        predicted_bag.append(predicted_vals)
        min_val_loss = min(fitting_results.history['val_loss'])
        min_val_loss_bag.append(min_val_loss)
    
    predicted_bag_array = np.concatenate(predicted_bag, axis=1)  
    min_val_loss_bag_array = np.array(min_val_loss_bag)
    weighted_preds = exp_bag_weighted_avg(min_val_loss_bag_array, 
                                          predicted_bag_array)
    
    return min_val_loss_bag_array, weighted_preds


def check_num_layers(features_in, target_vals, num_layers_list, eps, 
                     testing_X):
    
    num_CPU_cores = 6
    if len(tf.config.list_physical_devices('GPU')) > 0:
        split_GPU(6, 1024)
        GPU_mode = True
    bag_quantity = 3
    
    # make a folder to save model weights for ModelCheckpoint
    # need to do this before multiprocessing starts
    if not os.path.isdir('model_saves'):
        os.mkdir('model_saves')
    
    
    if not GPU_mode:
        pool_input = []
        for i in num_layers_list:
            pool_input.append((features_in, target_vals, bag_quantity, int(i), 
                               eps, testing_X))
        with Pool(num_CPU_cores) as p:
            pool_results = p.starmap(bag_models, pool_input)
    
    if GPU_mode:
        pool_results = []
        gpus = tf.config.list_logical_devices('GPU')
        for gpu in gpus:
            with tf.device(gpu.name):
                pool_results.append(bag_models(features_in, target_vals, 
                                               bag_quantity, int(i), 
                                               eps, testing_X))
    
    # only want fitting results (history object) for this function
    cost_comp = []
    for pool_result in pool_results:
        cost_comp.append(pool_result[0])
           
    return dict(zip(num_layers_list, cost_comp))


def divide_chunks(list_in, len_chunk):       
    # looping till length l 
    for i in range(0, len(list_in), len_chunk):  
        yield list_in[i:i + len_chunk] 


def make_num_layers_list(start_num, end_num, test_num):
    float_array = np.logspace(np.log2(start_num), np.log2(end_num), 
                              num=test_num, base=2)
    int_array = float_array.astype(int)
    remove_dups_set = set(int_array)
    ordered_list = list(remove_dups_set)
    ordered_list.sort()
    
    return ordered_list


def gen_max_num_layers(num_features):
    # defined so that num_features = 1 -> max_num_layers = 128
    # num_features = 16 -> max_num_layers = 64
    b = -np.log(0.5) / 15
    a = 128 / np.exp(-b)
    # lowest should be 32
    max_num_layers = max(32, int(a*np.exp(-b*num_features))) 
    
    return max_num_layers


def find_best_num_layers(features_in, target_vals, testing_X):
    
    # check inputs
    if not tf.is_tensor(features_in):
        features_in = tf.convert_to_tensor(features_in)
    if not tf.is_tensor(target_vals):
        target_vals = tf.convert_to_tensor(target_vals)
    if not tf.is_tensor(testing_X):
        testing_X = tf.convert_to_tensor(testing_X)
    if features_in.shape[0] != target_vals.shape[0]:
        raise ValueError('Num. of rows of features and targets must be equal.')
    
    num_features = get_num_features(features_in)
    
    broad_search_start = 2
    broad_search_end = gen_max_num_layers(num_features)
    broad_search_elements = 4
    broad_search_eps = 500
    broad_search_list = make_num_layers_list(broad_search_start, 
                                             broad_search_end,
                                             broad_search_elements)
    broad_search_results = check_num_layers(features_in, target_vals, 
                                            broad_search_list, 
                                            broad_search_eps,
                                            testing_X)
    
    return broad_search_results
    