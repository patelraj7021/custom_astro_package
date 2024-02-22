# -*- coding: utf-8 -*-
"""
Created on Mon Feb 19 01:19:13 2024

@author: patel
"""

import sys
import os
import pytest
from multiprocessing import Pool
sys.path.append(os.path.dirname(os.getcwd())) 
from src.temp_proj_name import NNOptimization
import keras
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import tensorflow as tf
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '0'



# working input cases
@pytest.fixture(params=[
                (3, 8, 'relu', 'linear', 4), 
                (1, 4, 'relu', 'linear', 10)
                ])  
def create_model_arch(request):
    in_params = request.param
    model_out = NNOptimization.init_model_arch(*in_params)
    return in_params, model_out


# test the init_model_arch function
class TestNNArch:
    
    # error input cases
    @pytest.mark.parametrize('in_params, exp_output', [
                                (('3', 8, 'relu', 'linear', 4), TypeError),
                                ((3, 8., 'relu', 'linear', 4), TypeError),
                                ((3, 8, 'relu', 'linear', [4]), TypeError),
                                ((0, 8, 'relu', 'linear', 4), ValueError),
                                ((3, 0, 'relu', 'linear', 4), ValueError),
                                ((3, 8, 'relu', 'linear', 0), ValueError),
                                ((3, 8, 'notreal', 'linear', 0), ValueError),
                                ((3, 8, 'relu', 'notreal', 0), ValueError),
                                ((3, 8, 1, 'linear', 4), TypeError),
                                ((3, 8, 'relu', 24, 4), TypeError)
                                # check for invalid activation inputs
                            ])
    def test_input_errors(self, in_params, exp_output):
        assert pytest.raises(exp_output, NNOptimization.init_model_arch, *in_params)
    
    
    # rest of these uses the working input cases
    def test_num_layers(self, create_model_arch):
        in_params, model_out = create_model_arch
        # len(*.layers) returns output layer too, so minus 1 for that
        assert len(model_out.layers) - 1 == in_params[0] 

    def test_num_nodes(self, create_model_arch):
        in_params, model_out = create_model_arch
        first_layer_config = model_out.get_layer(index=0).get_config()
        assert first_layer_config['units'] == in_params[1]
        
    def test_num_inputs(self, create_model_arch):
        in_params, model_out = create_model_arch
        input_layer_config = model_out.get_layer(index=0).get_build_config()
        assert input_layer_config['input_shape'] == (None, in_params[4])
        
    def test_activation_func(self, create_model_arch):
        in_params, model_out = create_model_arch
        first_layer_config = model_out.get_layer(index=0).get_config()
        assert first_layer_config['activation'] == in_params[2]
    
    def test_output_func(self, create_model_arch):
        in_params, model_out = create_model_arch
        output_layer_config = model_out.get_layer(index=-1).get_config()
        assert output_layer_config['activation'] == in_params[3]
        
    
        

if __name__=='__main__':
    temp = tf.constant([[2., 3., 4.],
                        [1., 2., 3.,]])
    print(temp.shape)
    # pytest.main()