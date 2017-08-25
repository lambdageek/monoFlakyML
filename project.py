import time
import datetime
import json

#pip install requests
import requests

#pip install scikit-learn, make sure numpy and scipy are already installed
from sklearn import svm
from sklearn.cluster import KMeans

#ensure pandas and numpy are installed
import pandas as pd
import numpy as np

#pip install plotly, external plotting & graphing library w/ tons of features
import plotly
import plotly.graph_objs as graph_objs
plotly.offline.init_notebook_mode();

### get the raw data
apiBaseUrl = 'https://monobi.azurewebsites.net/api/Get'
parameters = [];

prevTimeConst = 7; #constant for prevTimeConst days ago as timeframe for data collection
prevTime = (datetime.datetime.now() - datetime.timedelta(days=prevTimeConst)).strftime('%Y-%m-%d');
laterThanParameter = 'laterThan=' + prevTime;
parameters.append(laterThanParameter)

apiUrl = apiBaseUrl;
for i in range (0, len(parameters)):
	if i == 0:
		apiUrl += "?";
	else:
		apiUrl += "&";
	apiUrl += parameters[i];

print ("fetching from URL: ", apiUrl);

results = requests.get(apiUrl).json();
###

#converts datetime to integer
def dateTimeToInteger(dt, format):
	timestamp = time.mktime(datetime.datetime.strptime(dt, format).timetuple());
	return timestamp

#normalize integer function
def normalizeInteger(input, min, max, scale=1.0):
	return scale * ((input - min)* 1./(max-min))

now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S");
prevTimeTimestamp = dateTimeToInteger(prevTime, "%Y-%m-%d");
nowTimestamp = dateTimeToInteger(now, "%Y-%m-%dT%H:%M:%S");
timeScale = 10; #constant used to specify the range of the time (from 0 to timeScale)

### preprocessing - convert the data
failedTestMap = dict();
failedTestClusterMap = dict();

for result in results:
	if len(result["FailedTests"]):
		failedTests = result["FailedTests"];
		for failedTest in failedTests:
			key = failedTest["TestName"];

			if not key in failedTestMap:
				failedTestMap[key] = [];

			failedTestMap[key].append({
				"JobName": result["JobName"],
				"PlatformName": result ["PlatformName"],
				"DateTime": result["DateTime"]
			});
###

#global set of known flaky tests & reliable tests
knownFlakyTests = set(["MonoTests.System.Net.Sockets.SocketTest.SendAsyncFile", "MonoTests.DebuggerTests.Dispose", "MonoTests.System.ServiceModel.Web.WebServiceHostTest.ServiceBaseUriTest", "MonoTests.System.Net.HttpRequestStreamTest.CanRead"]);
knownReliableTests = set(["MonoTests.System.Threading.WaitHandleTest.WaitAnyWithSecondMutexAbandoned", "MonoTests.runtime.thread-suspend-selfsuspended.exe", "MonoTests.System.Threading.Tasks.TaskTests.Delay_Simple"]);


#processing for Count vs Timestamp failures, used for SVM
upperTimeScaleLimit = timeScale + 1;
for result in results:
	if len(result["FailedTests"]):
		failedTests = result["FailedTests"];

		for failedTest in failedTests:
			key = failedTest["TestName"];

			if not key in failedTestClusterMap:
				failedTestClusterMap[key] = {};

			gitHash = result["GitHash"];

			if not gitHash in failedTestClusterMap[key]:
				failedTestClusterMap[key][gitHash] = {
					"TimeStamp": upperTimeScaleLimit,
					"Count": 0
				}

			dateTime = result["DateTime"];
			dateTimeInt = dateTimeToInteger(dateTime[:19], "%Y-%m-%dT%H:%M:%S");
			normalizedTimeInt = normalizeInteger(dateTimeInt, prevTimeTimestamp, nowTimestamp, timeScale)

			if normalizedTimeInt < failedTestClusterMap[key][gitHash]["TimeStamp"]:
				failedTestClusterMap[key][gitHash]["TimeStamp"] = normalizedTimeInt
			failedTestClusterMap[key][gitHash]["Count"] += 1;


#processing for K-means 3D clustering of JobName & PlatformName vs Timestamp of individual failure points (a failed test point for a given commit)
testNameMap = dict(); #maps testname to integer
intTestNameMap = dict(); #maps integer to testname
jobNameMap = dict();
intJobNameMap = dict();
platformNameMap = dict();
intPlatformNameMap = dict();

kmeans3dInput = [];
kmeansClean3dInput = [];

flakyIndices = [];
reliableIndices = [];

def parseBuilds(key, builds):
	if key not in testNameMap:
		testNameMap[key] = len(intTestNameMap);
		intTestNameMap[len(intTestNameMap)] = key;
	assignedTestNameInt = testNameMap[key];

	for build in builds:
			jobName = build["JobName"];
			platformName = build["PlatformName"];

			if jobName not in jobNameMap:
				jobNameMap[jobName] = len(intJobNameMap);
				intJobNameMap[len(intJobNameMap)] = jobName;
			assignedJobNameInt = jobNameMap[jobName];

			if platformName not in platformNameMap:
				platformNameMap[platformName] = len(intPlatformNameMap);
				intPlatformNameMap[len(intPlatformNameMap)] = platformName;
			assignedPlatformNameInt = platformNameMap[platformName];

			unixTimestamp = dateTimeToInteger(build["DateTime"][:19], "%Y-%m-%dT%H:%M:%S");
			kmeans3dInput.append([assignedJobNameInt, assignedPlatformNameInt, normalizeInteger(unixTimestamp, prevTimeTimestamp, nowTimestamp, timeScale)]);

			if key in knownFlakyTests:
				flakyIndices.append(len(kmeans3dInput)-1);
			elif key in knownReliableTests:
				reliableIndices.append(len(kmeans3dInput)-1);
			else:
				kmeansClean3dInput.append([assignedJobNameInt, assignedPlatformNameInt, normalizeInteger(unixTimestamp, prevTimeTimestamp, nowTimestamp, timeScale)]);

for key in failedTestMap:
	builds = failedTestMap[key];
	parseBuilds(key, builds);

kmeans3dFlakyInput = [];
kmeans3dReliableInput = [];

for i in flakyIndices:
	kmeans3dFlakyInput.append(kmeans3dInput[i]);
for i in reliableIndices:
	kmeans3dReliableInput.append(kmeans3dInput[i]);


###run K-means 3D clustering & plot graph
cluster_count = 3; #constant that specifies # of clusters to try and fit data in
kmeans3d = KMeans(n_clusters = cluster_count)
kmeans3d.fit(kmeansClean3dInput);
labels = kmeans3d.labels_;
centroids = kmeans3d.cluster_centers_;

#colorset constant for color values on graph
colorset = [];
colorset.append("rgb(60, 140, 215)"); #arbitrary color value
colorset.append("rgb(13, 120, 7)"); #arbitrary color value
colorset.append("rgb(53, 190, 107)"); #arbitrary color value
colorset.append("rgb(250, 19, 100)"); #red
colorset.append("rgb(23, 190, 207)"); #blue
#TODO colorset currently hardcoded only for cluster_count = 3, should change this if cluster_count > 3

markerSize_known = 5;
markerSize_unknown = 2;

dataset = [];

cluster_map = dict();
for i in range(0, len(labels)):
	label = labels[i];
	if not label in cluster_map:
		cluster_map[label] = [];
	cluster_map[label].append(kmeansClean3dInput[i]);

color_index = 0;
for key in cluster_map:
	group = cluster_map[key];
	scatter = dict(
		mode = "markers",
		name = "Unknown",
		type = "scatter3d",
		x = [e[0] for e in group],
		y = [e[1] for e in group],
		z = [e[2] for e in group],
		marker = dict (size = markerSize_unknown, color = colorset[color_index])
	);
	cluster = dict(
		alphahull = 7,
		opacity = .1,
		type = "mesh3d",
		x = [e[0] for e in group],
		y = [e[1] for e in group],
		z = [e[2] for e in group]
	);
	dataset.append(scatter);
	dataset.append(cluster);
	color_index += 1;

flaky_scatter = dict(
	mode = "markers",
	name = "Flaky",
	type = "scatter3d",
	x = [e[0] for e in kmeans3dFlakyInput],
	y = [e[1] for e in kmeans3dFlakyInput],
	z = [e[2] for e in kmeans3dFlakyInput],
	marker = dict (size = markerSize_known, color = colorset[3])
);
reliable_scatter = dict(
	mode = "markers",
	name = "Reliable",
	type = "scatter3d",
	x = [e[0] for e in kmeans3dReliableInput],
	y = [e[1] for e in kmeans3dReliableInput],
	z = [e[2] for e in kmeans3dReliableInput],
	marker = dict (size = markerSize_known, color = colorset[4])
);

dataset.append(flaky_scatter);
dataset.append(reliable_scatter);

layout = graph_objs.Layout(
	title = "K-means 3D clustering graph",
	scene=dict(
		xaxis=dict(
			title='X - Job Name (numericalized)'
		),
		yaxis=dict(
			title="Y - Platform Name (numericalized)"
		),
		zaxis=dict(
			title="Z - " + prevTimeConst + " day(s) timestamp (normalized)"
		)
	)
);
fig = dict(
	data = dataset,
	layout=layout
);
#plotly.offline.plot(fig);










#run and plot SVM (using an RBF kernel) on individual testpoints where a testpoint is a count of failures for a given timestamp of a test given a commit group (aggregated by oldest timestamp in the commit group)
gammaConst = 10; #constant for gamma value in RBF kernel
cConst = 10; #constant for C value in RBF kernel
flakyTests = [];
reliableTests = [];
unknownTests = [];

for key in knownReliableTests:
	if key in failedTestClusterMap:
		reliableTest = [];
		for gitHash in failedTestClusterMap[key]:
			info = failedTestClusterMap[key][gitHash];
			reliableTest.append([info["TimeStamp"], info["Count"]]);
		reliableTests.append(reliableTest);

for key in knownFlakyTests:
	if key in failedTestClusterMap:
		flakyTest = [];
		for gitHash in failedTestClusterMap[key]:
			info = failedTestClusterMap[key][gitHash];
			flakyTest.append([info["TimeStamp"], info["Count"]]);
		flakyTests.append(flakyTest);

for key in failedTestClusterMap:
	if not key in knownReliableTests and not key in knownFlakyTests:
		unknownTest = [];
		for gitHash in failedTestClusterMap[key]:
			info = failedTestClusterMap[key][gitHash];
			unknownTest.append([info["TimeStamp"], info["Count"]]);
		unknownTests.append((key, unknownTest));

x2d = [];
y2d = [];
appendedList = [];

for reliableTest in reliableTests:
	for datapoint in reliableTest:
		x2d.append(datapoint);
		y2d.append(0);
for flakyTest in flakyTests:
	for datapoint in flakyTest:
		x2d.append(datapoint);
		y2d.append(1);

input2d = [];
for pair in unknownTests:
	unknownTest = pair[1];
	for datapoint in unknownTest:
		input2d.append(datapoint);
		appendedList.append(pair[0]);

clf = svm.SVC(kernel="rbf", random_state=0, gamma=gammaConst, C=cConst);
clf.fit(x2d, y2d);

results = clf.predict(input2d)

print ("Results for SVM prediction on unknown tests (0 indicates reliable, 1 indicates flaky): ", results);

for i in range(0, len(results)):
	result = results[i];
	if result == 0:
		print ("Reliable deemed for test result: ", appendedList[i], " at index ", i);


#plot the results
colorset2d = [];
colorset2d.append("rgb(110, 209, 255)"); #blue
colorset2d.append("rgb(255, 122, 110)"); #red
markerSize_svm = 10;

dataset_svm = [];
flaky_points = [];
reliable_points = [];

for i in range(0, len(results)):
	if results[i] == 0:
		reliable_points.append(input2d[i]);
	else:
		flaky_points.append(input2d[i]);

dataset_svm.append(graph_objs.Scatter(
	x = [e[0] for e in reliable_points],
	y = [e[1] for e in reliable_points],
	mode = "markers",
	name="Reliable",
	marker = dict(
		size=markerSize_svm,
		color=colorset2d[0]
	)
))

dataset_svm.append(graph_objs.Scatter(
	x = [e[0] for e in flaky_points],
	y = [e[1] for e in flaky_points],
	mode = "markers",
	name="Flaky",
	marker = dict(
		size=markerSize_svm,
		color=colorset2d[1]
	)
))

layout_svm = graph_objs.Layout(
	title = "SVM graph",
	xaxis=dict(
		title='X - Timestamp'
	),
	yaxis=dict(
		title="Y - Count"
	),
	showlegend=True
)

figure_svm = dict(
	data = dataset_svm,
	layout = layout_svm
)
#plotly.offline.plot(figure_svm)










#plot the testpoints for a given test where a testpoint is a count of failures for a given timestamp of a test given a commit group (aggregated by oldest timestamp in the commit group)
#2d graph of timestamp vs counts for a given test where each count value is aggregated by commit group (earliest timestamp in commit group is used as the timestamp)
#to change the test we want to view, simply change the testName constant to a valid name of a test
failedTestClusterMap;
dataset2d = [];

testName = "MonoTests.System.Net.Sockets.SocketTest.SendAsyncFile";

markerSize2d = 10;

points = [];
for gitHash in failedTestClusterMap[testName]:
	info = failedTestClusterMap[testName][gitHash];
	points.append((info["TimeStamp"], info["Count"]));

scatter2d = graph_objs.Scatter(
	x = [e[0] for e in points],
	y = [e[1] for e in points],
	mode = "markers",
	marker = dict(
		size=markerSize2d,
		color=colorset2d[1]
	)
)

layout2d = graph_objs.Layout(
	title = "Test Clustering Graph - " + testName,
	xaxis=dict(
		title='X - Timestamp'
	),
	yaxis=dict(
		title="Y - Count"
	)
)

dataset2d.append(scatter2d);
figure2d = dict(
	data = dataset2d,
	layout = layout2d
)
#plotly.offline.plot(figure2d)