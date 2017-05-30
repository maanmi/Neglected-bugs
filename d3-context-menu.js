//Based on https://www.npmjs.com/package/d3-context-menu
d3.contextMenu = function (openCallback) {
    // create the div element that will hold the context menu
    d3.selectAll('.d3-context-menu')
        .data([1])
        .enter()
        .append('div')
        .attr('class', 'd3-context-menu');
    // close menu
    d3.select('body')
        .on('click.d3-context-menu', function () {
            d3.select('.d3-context-menu')
                .style('display', 'none');
        });
    // this gets executed when a contextmenu event occurs
    return function (data, index) {
        var elm = this;
        var date = x.invert(d3.mouse(this)[0]);
        var dateTxt = d3.time.format("%Y-%m")(date),
            menu = []
        if (dateDict[dateTxt]) {
            dateDict[dateTxt].map(function (d) {
                menu.push({ title: '<a target="_blank" href="https://www.ncbi.nlm.nih.gov/pubmed/?term=' + d.pmid + '">' + d.genus + '</a>' })
            })
        } else {
            d3.event.preventDefault(); //don't show menu if there is no pubs
            return;
        }
        d3.selectAll('.d3-context-menu')
            .html('');
        var list = d3.selectAll('.d3-context-menu')
            .append('ul');
        list.selectAll('li')
            .data(menu)
            .enter()
            .append('li')
            .html(function (d) {
                return d.title;
            });
        // the openCallback allows an action to fire before the menu is displayed
        // an example usage would be closing a tooltip
        if (openCallback) openCallback(data, index);
        // display context menu
        d3.select('.d3-context-menu')
            .style('left', (d3.event.pageX - 2) + 'px')
            .style('top', (d3.event.pageY - 2) + 'px')
            .style('display', 'block');
        d3.event.preventDefault();
    };
};