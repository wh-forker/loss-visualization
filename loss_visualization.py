import caffe
import lmdb
import numpy as np
import os
import copy
import time
import math
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


def get_gaussian_vector(param_count=0,
                        vector_count=0):
    """
    This function generates a number of random gaussian vectors of length param count
    :param param_count: The number of random values to be generated
    :param vector_count: The number of random gaussian vectors to be generated
    :return: A numpy matrix of random Gaussian vectors
    """
    if param_count == 0 or vector_count == 0:
        return 0
    # This samples from a uniform distribution between 0 and 1, with param_count columns
    # and vector_count rows
    vectors = np.random.normal(loc=0, scale=1, size=(1, param_count))
    for idx in range(1, vector_count):
        curr_vec = np.random.normal(loc=0, scale=1, size=(1, param_count))
        mean = np.mean(curr_vec)
        std_dev = np.std(curr_vec)
        curr_vec = np.subtract(curr_vec, mean)
        if std_dev != 0:
            curr_vec = np.divide(curr_vec, std_dev)
        vectors = np.row_stack((vectors, curr_vec))
    return vectors


def calculate_norm(input_matrix=None):
    """
    This function calculates the Frobenius norm of an input matrix
    :param input_matrix: The input matrix of which the Frobenius norm is to be calculated
    This function assumes that each row is an independent vector and calculates the norm for
    each row
    :return: The Frobenius norm of each row in the matrix
    """
    if input_matrix is None:
        return 0

    return np.sqrt(np.sum(input_matrix * input_matrix, axis=1))


def save_network_weights(net=None):
    if net is None:
        return None

    layer_names = net.blobs
    net_weights = dict()
    for layer in layer_names:
        curr_layer = net.layer_dict.get(layer, None)
        if curr_layer is None:
            continue
        if net.layer_dict.get(layer, None).type in ('Convolution', 'InnerProduct'):
            layer_data = {'weights': np.array(net.params[layer][0].data.flat, copy=True),
                          'bias': np.array(net.params[layer][1].data.flat, copy=True)}
            net_weights[layer] = copy.deepcopy(layer_data)

    return copy.deepcopy(net_weights)


def update_net_params(net, layer_weights, vector1, vector2):
    """
    This function updates the network weights obtained from the initial weights
    :param net: The CAFFE network
    :param layer_weights: The saved weights
    :param vector1: The vector whose weights are to be added to the network
    :param vector2: THe vector whose weights are to be added to the network
    :return:
    """
    layer_names = net.blobs

    # iterate through all the layers
    for layer in layer_names:
        curr_layer = net.layer_dict.get(layer, None)
        if curr_layer is None:
            continue

        vec_idx = 0
        # Update only convolutional and fully connected layers
        if net.layer_dict.get(layer, None).type in ('Convolution', 'InnerProduct'):

            # Update the weights of the layer
            layer_length = np.shape(net.params[layer][0].data.flat)[0]
            weights = layer_weights.get(layer).get('weights')
            net.params[layer][0].data.flat = weights + \
                                             vector1[vec_idx:vec_idx + layer_length] + \
                                             vector2[vec_idx:vec_idx+layer_length]
            vec_idx = vec_idx + layer_length

            # Update the biases of the layer
            bias_values = layer_weights.get(layer).get('bias')
            bias_length = net.params[layer][1].data.shape[0]
            net.params[layer][1].data.flat = bias_values  + \
                                        vector1[vec_idx:vec_idx + bias_length] + \
                                        vector2[vec_idx:vec_idx + bias_length]

            vec_idx = vec_idx + bias_length


    return net


def create_grid(vectors=None, steps=0):
    """
    This function creates a square grid of values between the starting and ending vectors defined by steps
    :param vectors: The starting and ending vectors
    :param steps: The number of steps from the starting to ending values
    :return: A matrix of size steps X number of columns in the vector
    """
    if vectors is None or steps == 0:
        return None

    # Get the shape of the vectors
    vector_shape = list(np.shape(vectors))
    if vector_shape[0] != 2:
        return None

    # Create the range of values for each value in the vector with the initial value
    # at row 0 and final value at row 1 for any column in the vectors
    value_matrix = np.linspace(vectors[0][0], vectors[1][0], num=steps).reshape(steps, 1)
    for col in range(1, vector_shape[1]):
        value_matrix = np.hstack([value_matrix, \
                                  np.linspace(vectors[0][col], vectors[1][col], num=steps).reshape(steps, 1)])

        if col % 1000 == 0:
            print('Completed :', col,'/',vector_shape[1])

    return value_matrix


def create_loss_landscape(net=None, vectors=None, best_image=None, best_label=None,
                          worst_image=None, worst_label=None, dir=None, steps=0, lmdb_env=None, mean_path=None):
    """
    This function creates a grid with the vectors to visualize the loss landscape of the network
    :param net: The Neural Network whose loss landscape is to be visualized
    :param vectors: The normalized gaussian vectors
    :param best_image: image with the highest correctly classified probability to be tested
    :param best_label: label of the image
    :param worst_image: correctly classified image with the worst probability
    :param worst_label: label of the image
    :param dir: The path of the directory where the numpy grid values are to be written
    :param steps: The number of steps in the grid
    :return: A matrix containing the loss values for each point in the grid
    """
    debug = 1
    start_time = time.time()
    # if not debug, calculate the grid and save the new data
    if not debug or not(os.path.exists(os.path.join(dir,'vector_grid1.npy')) and
                        os.path.exists(os.path.join(dir,'vector_grid2.npy'))):
        vector_grid1 = create_grid(np.vstack((vectors[0], np.negative(vectors[0]))), steps)
        vector_grid2 = create_grid(np.vstack((vectors[1], np.negative(vectors[1]))), steps)

        np.save(os.path.join(dir, 'vector_grid1'), vector_grid1)
        np.save(os.path.join(dir, 'vector_grid2'), vector_grid2)
    else:
        vector_grid1 = np.load(os.path.join(dir, 'vector_grid1.npy'))
        vector_grid2 = np.load(os.path.join(dir, 'vector_grid2.npy'))

    end_time = time.time() - start_time
    print('Duration : ' + str(end_time))

    # Save the initial weights of the network
    layer_weights = save_network_weights(net=net)

    out = net.forward(data=np.asarray([best_image]))
    predicted_label = out['prob'][0][best_label]
    print('Default Loss:', -(math.log(predicted_label)))

    loss_matrix = np.zeros((steps, steps))
    accuracy_matrix = np.zeros((steps, steps))
    best_image_loss = np.zeros((steps, steps))
    best_image_accuracy = np.zeros((steps, steps))
    worst_image_loss = np.zeros((steps, steps))
    worst_image_accuracy = np.zeros((steps, steps))
    for x_idx in range(0, steps):
        for y_idx in range(0, steps):
            print(x_idx, y_idx)
            # Modify the network values
            net = update_net_params(net, layer_weights, vector_grid1[x_idx, :], vector_grid2[y_idx, :])

            # Calculate the loss for the entire testing database

            loss, accuracy = compute_loss_for_db(net=net, lmdb_env=lmdb_env, mean_file_path=mean_path)

            if loss == 0:
                loss = math.nan
            else:
                loss = -(math.log(loss))
            # Save the loss value to a matrix
            print(loss)
            loss_matrix[x_idx][y_idx] = loss
            accuracy_matrix[x_idx][y_idx] = accuracy


            softmax_loss_dict = net.forward(data=np.asarray([best_image]))
            loss_best = softmax_loss_dict['prob'][0][best_label]
            predicted_label = softmax_loss_dict['prob'].argmax()
            if loss_best == 0:
                loss_best = math.nan
            else:
                loss_best = -(math.log(loss_best))
            best_image_loss[x_idx][y_idx] = loss_best
            if predicted_label == best_label:
                best_image_accuracy[x_idx][y_idx] = 1
            else:
                best_image_accuracy[x_idx][y_idx] = 0

            softmax_loss_dict = net.forward(data=np.asarray([worst_image]))
            loss_worst = softmax_loss_dict['prob'][0][worst_label]
            predicted_label = softmax_loss_dict['prob'].argmax()
            if loss_worst == 0:
                loss_worst = math.nan
            else:
                loss_worst = -(math.log(loss_worst))
            worst_image_loss[x_idx][y_idx] = loss_worst
            if predicted_label == worst_label:
                worst_image_accuracy[x_idx][y_idx] = 1
            else:
                worst_image_accuracy[x_idx][y_idx] = 0


    return loss_matrix, accuracy_matrix, best_image_loss, best_image_accuracy, worst_image_loss, worst_image_accuracy


def calculate_param_count(net=None):
    """
    This function calculates the number of parameters in the Caffe Network
    :param net: The caffe network that has been loaded
    :return: The number of parameters and its Frobenius Norm
    """
    if net is None:
        return None

    param_count = 0
    norm = 0
    layer_names = net.blobs
    for layer in layer_names:
        curr_layer = net.layer_dict.get(layer, None)
        if curr_layer is None:
            continue
        if net.layer_dict.get(layer, None).type in ('Convolution', 'InnerProduct'):
            curr_layer_shape = net.params[layer][0].data.shape
            norm = norm + (net.params[layer][0].data * net.params[layer][0].data).sum()
            norm = norm + (net.params[layer][1].data * net.params[layer][1].data).sum()
            layer_params = 1
            for layer_shape in curr_layer_shape:
                layer_params = layer_params * layer_shape

            bias_params = net.params[layer][1].data.shape
            param_count = param_count + layer_params + bias_params[0]

    norm = np.sqrt(norm)
    return param_count, norm


def compute_loss_for_db(net=None, lmdb_env=None, mean_file_path=None):
    lmdb_txn = lmdb_env.begin()
    lmdb_cursor = lmdb_txn.cursor()
    count = 0
    correct = 0
    worst_prob = 1
    best_prob = 0
    blob = caffe.proto.caffe_pb2.BlobProto()
    mean_image_binary = open(mean_file_path, 'rb').read()
    blob.ParseFromString(mean_image_binary)
    mean_image = np.array(caffe.io.blobproto_to_array(blob))
    mean_image = np.reshape(mean_image, newshape=(3, 32, 32))
    caffe.set_mode_gpu()
    max_prob = 0
    loss = 0
    accuracy = 0
    for key, value in lmdb_cursor:
        count = count + 1
        datum = caffe.proto.caffe_pb2.Datum()
        datum.ParseFromString(value)
        label = int(datum.label)
        image = caffe.io.datum_to_array(datum)
        image = (image - mean_image)
        out = net.forward(data=np.asarray([image]))
        predicted_label = out['prob'].argmax()
        curr_prob = out['prob'][0][label]
        loss = loss + curr_prob
        if label == predicted_label:
            correct = correct + 1
        # print("Label is class " + str(label) + ", predicted class is " + str(predicted_label))
        if count == 10000:
            break

    #lmdb_env.close()
    # Average loss and accuracy for the updated net
    loss = (loss/count)
    accuracy = correct/count
    print(str(correct) + " out of " + str(count) + " were classified correctly")
    return loss, accuracy


def main():
    #MODEL_FILE = '/home/chris/PycharmProjects/loss-visualization/models/quick_learn/solver.prototxt'
    #PRETRAINED = '/home/chris/PycharmProjects/loss-visualization/models/quick_learn/model.caffemodel'
    DB_PATH = '/home/chris/caffe/examples/cifar10/cifar10_test_lmdb'
    MEAN_FILE_PATH = '/home/chris/caffe/python/mean.binaryproto'
    #MODEL_FILE = '/home/chris/caffe/python/deploy.prototxt'
    #PRETRAINED = '/home/chris/caffe/python/model.caffemodel'

    '''
    MODEL_FILE = filedialog.askopenfilename(type='*.prototxt')
    PRETRAINED = filedialog.askopenfilename(type='*.caffemodel')
    DB_PATH = filedialog.askdirectory()
    MEAN_FILE_PATH = filedialog.askopenfilename(type='*.binaryproto')
    '''
    dir = '/home/chris/PycharmProjects/loss-visualization/models/sigmoid'
    steps = 51
    MODEL_FILE = os.path.join(dir, 'solver.prototxt')
    PRETRAINED = os.path.join(dir, 'model.caffemodel')
    MEAN_FILE_PATH = os.path.join(dir,'mean.binaryproto')
    net = caffe.Net(MODEL_FILE, PRETRAINED, caffe.TRAIN)
    lmdb_env = lmdb.open(DB_PATH)
    lmdb_txn = lmdb_env.begin()
    lmdb_cursor = lmdb_txn.cursor()
    count = 0
    correct = 0
    worst_prob = 1
    best_prob = 0
    blob = caffe.proto.caffe_pb2.BlobProto()
    mean_image_binary = open(MEAN_FILE_PATH, 'rb').read()
    blob.ParseFromString(mean_image_binary)
    mean_image = np.array(caffe.io.blobproto_to_array(blob))
    mean_image = np.reshape(mean_image, newshape=(3,32,32))
    caffe.set_mode_gpu()
    max_prob = 0
    for key, value in lmdb_cursor:
        count = count + 1
        datum = caffe.proto.caffe_pb2.Datum()
        datum.ParseFromString(value)
        label = int(datum.label)
        image = caffe.io.datum_to_array(datum)
        image = (image - mean_image) #* 0.0078125
        # out = net.forward_all(data=np.asarray([image]))
        #net.blobs['data'].data[...] = image
        #net.blobs['label'].data[...] = label
        #out = net.forward()
        out = net.forward(data=np.asarray([image]))
        predicted_label = out['prob'].argmax()
        curr_prob = out['prob'][0][predicted_label]
        if label == predicted_label:
            correct = correct + 1
            correct_image = image
            correct_label = label
            max_prob = curr_prob
            if curr_prob > best_prob:
                best_image = image
                best_prob = curr_prob
                best_label = label

            if curr_prob < worst_prob:
                worst_image = image
                worst_label = label
                worst_prob = curr_prob
        # print("Label is class " + str(label) + ", predicted class is " + str(predicted_label))
        if count == 10000:
            break

    #lmdb_env.close()
    print(str(correct) + " out of " + str(count) + " were classified correctly")

    # Get the normalized Gaussian vectors for the total number of parameters
    # Vector count is currently 2 because only two vectors are needed in x and y directions
    vector_count = 2
    # Calculate the total parameter count in the network
    # Calculate the Frobenius norm/Euclidean norm of the network
    # Square root of sum of absolute squares of all the weights in the network
    param_count, euclidean_norm = calculate_param_count(net)
    print(param_count)
    gaussian_vec = get_gaussian_vector(param_count, vector_count)

    # Normalize the Gaussian Vector with the norm
    vectors_norms = calculate_norm(gaussian_vec)
    normalized_vectors = np.divide(gaussian_vec, np.reshape(vectors_norms, [len(vectors_norms), 1]))

    # Multiply the vectors with the norm of the Network
    directional_vectors = np.multiply(normalized_vectors, euclidean_norm)

    # save the matrix of directional_vectors
    # save the numpy array
    np.save('directional_vectors', directional_vectors)

    loss, accuracy, best_image_loss_values, best_image_accuracy, worst_image_loss_values, worst_image_accuracy = create_loss_landscape(net, directional_vectors, best_image, best_label,
                                                        worst_image, worst_label, dir, steps=steps, lmdb_env=lmdb_env,
                                                        mean_path=MEAN_FILE_PATH)

    #x = y = np.arange(-3.5, 4.0, 0.5)
    x = y = np.linspace(-1.0, 1.0, num=best_image_loss_values.shape[0] )
    X, Y = np.meshgrid(x, y)
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.plot_surface(X, Y, best_image_loss_values)
    plt.show()

    np.savetxt(os.path.join(dir, 'loss.csv'), loss, delimiter=",")
    np.savetxt(os.path.join(dir, 'accuracy.csv'), accuracy, delimiter=",")
    np.savetxt(os.path.join(dir, 'best_loss.csv'), best_image_loss_values, delimiter=",")
    np.savetxt(os.path.join(dir, 'best_accuracy.csv'), best_image_accuracy, delimiter=",")
    np.savetxt(os.path.join(dir, 'worst_loss.csv'), worst_image_loss_values, delimiter=",")
    np.savetxt(os.path.join(dir, 'worst_accuracy.csv'), worst_image_accuracy, delimiter=",")


if __name__ == '__main__':
    main()