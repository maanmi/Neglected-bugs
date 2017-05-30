// Used ideas from:
// https://flowingdata.com/2013/01/17/how-to-animate-transitions-between-multiple-charts/ 
// http://www.d3noob.org/2014/07/my-favourite-tooltip-method-for-line.html
// http://bl.ocks.org/rkirsling/33a9e350516da54a5d4f

var svgWidth = 800,
    svgHeight = 400,
    margin = {
        top: 10,
        right: 25,
        bottom: 50,
        left: 35},
    dateDict = new Object(),
    y, y_multi, y_stacked,
    cumulative = false, stacked = false;


var chartWidth = svgWidth - margin.left - margin.right,
    chartHeight = svgHeight - margin.top - margin.bottom;

var parseDate = d3.time.format("%Y-%m").parse;

// Switch toggle
$('.Switch')
    .click(function () {
        $(this)
            .toggleClass('On')
            .toggleClass('Off');
        stacked = (!cumulative && !stacked) ? true : false;
        toggle_switch_update();
    });

createLegend();

d3.tsv(dataset, function (rawData) {

    var data = new dataProcess(rawData);

    // Set scales
    x = d3.time.scale().range([0, chartWidth])
        .domain([d3.min(data, function (d) {
            return d.values[0].date}), d3.max(data, function (d) {
                  return d.values[d.values.length - 1].date
              })]),
    y_multi = d3.scale.linear().range([chartHeight, 0])
        .domain([0, d3.max(data, function (d) {
            return d3.max(d.values, function (dd) {
                return dd.count;
            })
        })])
    y_stacked = d3.scale.linear().range([chartHeight, 0])
        .domain([0, d3.max(data, function (d) {
            return d3.max(d.values, function (dd) {
                return dd.y + dd.y0;
            })
        })]);

    // Initialize chart on multi-area state
    y = y_multi;

    // Draw axes
    var xAxis = d3.svg.axis()
        .scale(x)
        .orient('bottom')
        .innerTickSize(-chartHeight)
        .outerTickSize(0)
        .tickPadding(20)
        .tickFormat(d3.time.format("%Y"));

    var yAxis = d3.svg.axis()
        .scale(y)
        .orient('left')
        .innerTickSize(-chartWidth)
        .outerTickSize(0)
        .tickPadding(10)
        .tickFormat(d3.format("d"));

    var svg = d3.select('#chart1chart')
        .append('svg')
        .attr('width', svgWidth)
        .attr('height', svgHeight)
        .append('g')
        .attr('transform', 'translate(' + margin.left + ',' + margin.top + ')')
        .on('dblclick', function () {
            d3.selectAll('.area')
                .transition()
                .style('opacity', 0.7)
        })
        .on('contextmenu', d3.contextMenu());


    // Clipping to start chart hidden and slide it in later
    var rectClip = svg.append('clipPath')
        .attr('id', 'rect-clip')
        .append('rect')
        .attr('width', 0)
        .attr('height', chartHeight);

    svg.append("rect")
        .attr("width", chartWidth)
        .attr("height", chartHeight)
        .style("fill", "none")
        .style("pointer-events", "all")
        .on("mouseover", function () {
            focus.style("display", null);
        })
        .on("mouseout", function () {
            focus.style("display", "none");
        })
        .on("mousemove", mousemove)
        .on("dblclick", function(){
             d3.selectAll('.area')
                .transition()
                .style('opacity', 0.7)
          });

    var axes = svg.append('g')
        .attr('clip-path', 'url(#axes-clip)');

    axes.append('g')
        .attr('class', 'x axis')
        .attr('transform', 'translate(0,' + chartHeight + ')')
        .call(xAxis)
        .selectAll('text')
        .attr("transform", "rotate(-45)")
        .attr("dy", ".35em")
        .style("text-anchor", "end")
        .append('text')
        .attr('y', 40)
        .attr('x', chartWidth - 20)
        .text('Date');

    axes.append('g')
        .attr('class', 'y axis')
        .call(yAxis)
        .append('text')
        .attr('transform', 'rotate(-90)')
        .attr('y', 6)
        .attr('dy', '.71em')
        .style('text-anchor', 'end')
        .text('No. publications');

    // Initiate graph
    update_graph(data);
  
    rectClip.transition()
            .duration(2000)
            .attr('width', chartWidth);

  
    // Create x axis tooltip
    focus = svg.append("g")
        .attr('class', 'tooltipline')
        .style("display", "none");

    focus.append("line")
        .style("stroke-dasharray", "3,3")
        .style("opacity", 0.5)
        .attr("y1", 0)
        .attr("y2", chartHeight);

    focus.append("circle")
        .style("fill", "none")
        .attr("r", 4);

    focus.append("text")
        .style("opacity", 0.8)
        .attr("dx", 8)

    // Checkbox toggle
    d3.selectAll("#checkbox input[name=field]")
        .on("change", function () {
            cumulative = this.value == 'cumulative' ? true : false;
            d3.select('.Switch')
                .style('pointer-events', function () {
                    return cumulative ? 'none' : 'all'
                })
            toggle_check_update(rawData);
        });
})

function toggle_switch_update() {
    y = stacked ? y_stacked : y_multi;

    var area = d3.svg.area()
        .interpolate("cardinal")
        .x(function (d) {
            return x(d.date) || 1;
        })
        .y0(function (d) {
            return stacked ? y(d.y0) : y(0);
        })
        .y1(function (d) {
            return stacked ? y(d.y0 + d.y) : y(d.count);
        })

    d3.selectAll('.area')
        .transition()
        .duration(500)
        .attr('d', area);

    update_yaxis();
}

function toggle_check_update(rawData) {
    cumulative ? completelyHideLegend() : hideLegend();

    var data = new dataProcess(rawData);

    // Update y axis based on new data
    y.domain([0, d3.max(data, function (d) {
        return d3.max(d.values, function (dd) {
            return dd.count;
        })
    })])

    var yAxis = d3.svg.axis()
        .scale(y)
        .orient('left')
        .innerTickSize(-chartWidth)
        .outerTickSize(0)
        .tickPadding(10)
        .tickFormat(d3.format("d"));

    d3.select('#chart1chart')
        .select(".y.axis")
        .transition()
        .duration(500)
        .call(yAxis);

    update_graph(data);
}

function update_graph(data) {

    var area = d3.svg.area()
        .interpolate("cardinal")
        .x(function (dd) {
            return x(dd.date) || 1;
        })
        .y0(y(0))
        .y1(function (dd) {
            return y(dd.count);
        });

    var path = d3.select('#chart1')
        .select('svg')
        .select('g')
        .selectAll(".area")
        .data(data.map(function (d) {
            return d.values
        }));

    path.enter()
        .append('path')
        .attr('clip-path', 'url(#rect-clip)');

    path.attr('class', function (d, i) {
            return 'area ' + data[i].key
        })
        .attr('fill', function (d, i) {
            var phylum = data[i].key;
            return cumulative ? 'grey' : '#' + colorScale[phylum]
        })
        .transition()
        .duration(500)
        .attr('d', area);

    path.exit().remove();
}

function update_yaxis() {

    var yAxis = d3.svg.axis()
        .scale(y)
        .orient('left')
        .innerTickSize(-chartWidth)
        .outerTickSize(0)
        .tickPadding(10)
        .tickFormat(d3.format("d"));

    d3.select('#chart1')
        .select(".y.axis")
        .transition()
        .duration(500)
        .call(yAxis);
}

function dataProcess(rawData) {
    // Extract all present dates:
    var dates = d3.map(rawData, function (d) {
            return d.date })
        .keys();

    var data = d3.nest()
        .key(function (d) {
            return cumulative ? 'all' : d.phylum
        })
        .rollup(function (leaves) {

            var group_by_date = d3.nest()
                .key(function (d) {
                    return d.date
                })
                .entries(leaves);

            var data_dates = group_by_date.map(function (d) {
                return d.key
            });
            // Fill in with all months, even if some  are not in the dataset (required for stacked layout)
            var aggregate_data = dates.map(function (date) {
                var pos = data_dates.indexOf(date);
                if (pos != -1) {
                    var d = group_by_date[pos];
                    dateDict[date] = d.values;
                    return {
                        'date': parseDate(date),
                        'count': d.values.length,
                        'values': d.values
                    }
                } else {
                    return {
                        'date': parseDate(date),
                        'count': 0,
                        'values': []
                    }
                }
            })
            return aggregate_data
        })
        .entries(rawData);

    var stack = d3.layout.stack()
        .offset("zero")
        .values(function (d) {
            return d.values;
        })
        .x(function (d) {
            return d.date;
        })
        .y(function (d) {
            return d.count;
        });

    //sort by date
    data.map(function (d) {
        d.values.sort(function (a, b) {
            return a.date - b.date
        })
    })

    return cumulative ? data : stack(data);
}

function mousemove() {
    var date = x.invert(d3.mouse(this)[0]),
        dateTxt = d3.time.format("%Y-%m")(date),
        color = '#ababab';

    // Emphasize months with publications:
    if (dateDict[dateTxt]) color = '#b300b3';
  
    focus.select("circle")
        .attr("transform", "translate(" + x(date) + ", 0)");
  
    focus.select("text")
        .attr("transform", "translate(" + x(date) + ", 0)")
        .text(dateTxt)
        .style('stroke', color);
  
    focus.select("line")
        .attr("transform", "translate(" + x(date) + ", 0)");
}

// Called on legend mouse over
function showLegend(d, i) {
    d3.select("#legend svg g.panel")
        .transition()
        .duration(500)
        .attr("transform", "translate(70," + margin.top * 5 + ")")
}

// Called on legend mouse out
function hideLegend(d, i) {
    d3.select("#legend svg g.panel")
        .transition()
        .duration(500)
        .attr("transform", "translate(158," + margin.top * 5 + ")")
}

// Called on cumulative view & when viewing other parts of the page
function completelyHideLegend(d, i) {
    d3.select("#legend svg g.panel")
        .transition()
        .duration(500)
        .attr("transform", "translate(500," + margin.top * 5 + ")")
}

function createLegend() {
    var legendWidth = 200,
        legendHeight = 245;

    var legend = d3.select("#legend")
        .append("svg")
        .attr("width", legendWidth)
        .attr("height", legendHeight);

    legendG = legend.append("g")
        .attr("class", "panel")
        .attr("transform", "translate(500," + margin.top * 5 + ")");

    legendG.append("rect")
        .attr("width", legendWidth)
        .attr("height", legendHeight)
        .attr("rx", 4)
        .attr("ry", 4)
        .attr("fill-opacity", 0.5)
        .attr("fill", "white");

    legendG.on("mouseover", showLegend)
        .on("mouseout", hideLegend);

    var keys = legendG.selectAll("g")
        .data(d3.map(colorScale).keys())
        .enter()
        .append("g")
        .attr("transform", function (d, i) {
            return "translate(5," + (30 * i) + ")"
        });

    keys.append("rect")
        .attr("width", 20)
        .attr("height", 20)
        .attr("rx", 4)
        .attr("ry", 4)
        .attr("fill", function (d) {
            return '#' + colorScale[d]
        })
  // On dblclick fade out all other phyla:
        .on('dblclick', function (d) {
            d3.selectAll('.area')
                .transition()
                .style('opacity', function () {
                    return d3.select(this)
                        .classed(d) ? 1 : 0.1
                })
        });

    keys.append("text")
        .text(function (d) {
            return d
        })
        .attr("text-anchor", "left")
        .attr("dx", "3em")
        .attr("dy", "1.3em");
}