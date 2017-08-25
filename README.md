# monoFlakyML
machine learning operations on the test failure dataset for mono based in Jenkins

This python script attempts to run a couple machine learning techniques on the test failure dataset for mono using a database that pulls from Jenkins
All the plot lines (which start with 'plotly.offline.plot') are commented out by default. To see any of the graphs for the respective result, just uncomment the plot line.

Since this script operates by pulling data from an azure portal connected to the database, if any changes to the database or azure affect how this query operates, then appropriate changes must be made to the script as well to keep it up-to-date.

There are a couple external dependencies/libraries that need to be installed prior to running the script. They should be noted in the import section.