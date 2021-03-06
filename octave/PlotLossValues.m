function PlotLossValues(path)
%data = csvread(path);
path
data = load(path);
data_end_point = floor(size(data,1)/2);
values = linspace(-1.0,1.0,size(data,1));
data(data==0) = min(data(data~=0)) / 2;
[XX, YY] = meshgrid(values, values);
figure, surf(XX, YY, log(data));
xlabel ("Random Gaussian Vector");
ylabel ("Random Gaussian Vector");
zlabel ("Logarithmic Loss")