// Global variables
let fanCurveChart = null;
let activeCurve = '';
let activeProfileName = '';
let curveVisibility = {
};
let fanCurves = {};

const MIN_TEMP = 20, MAX_TEMP = 90;
const MIN_SPEED = 0, MAX_SPEED = 100;
const MIN_POINTS = 2, MAX_POINTS = 20;
const CURVE_CLICK_TOLERANCE = 8;

// Color palette for curves
const COLOR_PALETTE = [
    {
        curveColor: 'rgba(59, 130, 246, 0.8)',      // Blue
        curveFill: 'rgba(59, 130, 246, 0.1)',
        pointColor: 'rgba(239, 68, 68, 0.9)',      // Red
        pointBorder: 'rgba(220, 38, 38, 1)',
    },
    {
        curveColor: 'rgba(16, 185, 129, 0.8)',      // Green
        curveFill: 'rgba(16, 185, 129, 0.1)',
        pointColor: 'rgba(245, 158, 11, 0.9)',      // Amber
        pointBorder: 'rgba(217, 119, 6, 1)',
    },
    {
        curveColor: 'rgba(168, 85, 247, 0.8)',     // Purple
        curveFill: 'rgba(168, 85, 247, 0.1)',
        pointColor: 'rgba(236, 72, 153, 0.9)',     // Pink
        pointBorder: 'rgba(219, 39, 119, 1)',
    },
    {
        curveColor: 'rgba(249, 115, 22, 0.8)',      // Orange
        curveFill: 'rgba(249, 115, 22, 0.1)',
        pointColor: 'rgba(34, 197, 94, 0.9)',      // Emerald
        pointBorder: 'rgba(22, 163, 74, 1)',
    },
    {
        curveColor: 'rgba(14, 165, 233, 0.8)',      // Sky
        curveFill: 'rgba(14, 165, 233, 0.1)',
        pointColor: 'rgba(251, 191, 36, 0.9)',     // Yellow
        pointBorder: 'rgba(217, 119, 6, 1)',
    },
    {
        curveColor: 'rgba(244, 63, 94, 0.8)',       // Rose
        curveFill: 'rgba(244, 63, 94, 0.1)',
        pointColor: 'rgba(99, 102, 241, 0.9)',      // Indigo
        pointBorder: 'rgba(79, 70, 229, 1)',
    },
    {
        curveColor: 'rgba(20, 184, 166, 0.8)',      // Teal
        curveFill: 'rgba(20, 184, 166, 0.1)',
        pointColor: 'rgba(251, 146, 60, 0.9)',     // Peach
        pointBorder: 'rgba(234, 88, 12, 1)',
    }
];

// Get color for curve based on index
function getCurveStyle(curveIndex) {
    return COLOR_PALETTE[curveIndex % COLOR_PALETTE.length];
}

// Ensure all curves have visibility settings
function ensureVisibilitySettings() {
    Object.keys(fanCurves).forEach(curveKey => {
        if (curveVisibility[curveKey] === undefined) {
            curveVisibility[curveKey] = true;
        }
    });
}

// Utility functions
function sortPointsByTemperature(curveData) {
    return curveData.sort((a, b) => a.x - b.x);
}

function constrainValue(value, min, max) {
    return Math.max(min, Math.min(max, value));
}

function generateExtendedCurve(points) {
    if (!points || points.length === 0) return [];
    
    const extended = [];
    const firstPoint = points[0];
    const lastPoint = points[points.length - 1];
    
    if (firstPoint.x > MIN_TEMP) {
        extended.push({x: MIN_TEMP, y: firstPoint.y, isExtension: true});
    }
    
    extended.push(...points.map(p => ({...p, isExtension: false})));
    
    if (lastPoint.x < MAX_TEMP) {
        extended.push({x: MAX_TEMP, y: lastPoint.y, isExtension: true});
    }
    
    return extended;
}

function interpolateFanSpeed(temperature, curveKey) {
    const curveInfo = fanCurves[curveKey];
    if (!curveInfo || !curveInfo.data || curveInfo.data.length === 0) return null;
    
    const sortedData = [...curveInfo.data].sort((a, b) => a.x - b.x);
    
    if (temperature <= sortedData[0].x) {
        return sortedData[0].y;
    }
    
    if (temperature >= sortedData[sortedData.length - 1].x) {
        return sortedData[sortedData.length - 1].y;
    }
    
    for (let i = 0; i < sortedData.length - 1; i++) {
        const point1 = sortedData[i];
        const point2 = sortedData[i + 1];
        
        if (temperature >= point1.x && temperature <= point2.x) {
            const ratio = (temperature - point1.x) / (point2.x - point1.x);
            return point1.y + (point2.y - point1.y) * ratio;
        }
    }
    
    return null;
}

function isClickNearCurve(clickX, clickY, curveKey) {
    if (!fanCurveChart) return false;
    
    const interpolatedSpeed = interpolateFanSpeed(clickX, curveKey);
    if (interpolatedSpeed === null) return false;
    
    const curvePixelY = fanCurveChart.scales.y.getPixelForValue(interpolatedSpeed);
    const clickPixelY = fanCurveChart.scales.y.getPixelForValue(clickY);
    
    const distance = Math.abs(clickPixelY - curvePixelY);
    return distance <= CURVE_CLICK_TOLERANCE;
}

function updatePointsDisplay() {
    const infoEl = document.getElementById('current-info');
    if (!infoEl || !fanCurves[activeCurve]) return;
    
    const activeData = fanCurves[activeCurve];
    
    let html = '';
    
    // Add CSS for hiding number input spinners and dark theme styling
    html += `<style>
        .number-input {
            -moz-appearance: textfield;
            background-color: #1d1d1d !important; /* Consistent dark background */
            color: #ffffff !important; /* White text */
            border-color: #4b5563 !important; /* Gray-600 border */
        }
        .number-input::-webkit-outer-spin-button,
        .number-input::-webkit-inner-spin-button {
            -webkit-appearance: none;
            margin: 0;
        }
        .number-input:focus {
            border-color: #3b82f6 !important; /* Blue border on focus */
            outline: none !important;
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2) !important; /* Blue glow */
        }
    </style>`;
    
    // Create editable inputs for each point
    activeData.data.forEach((point, index) => {
        // Calculate constraints for this point (same as drag constraints)
        const minX = (index > 0) ? activeData.data[index - 1].x + 1 : MIN_TEMP;
        const maxX = (index < activeData.data.length - 1) ? activeData.data[index + 1].x - 1 : MAX_TEMP;
        const minY = (index > 0) ? activeData.data[index - 1].y : MIN_SPEED;
        const maxY = (index < activeData.data.length - 1) ? activeData.data[index + 1].y : MAX_SPEED;
        
        html += `<div class="flex justify-between items-center py-1 border-b border-gray-100">
            <span class="text-sm">Point ${index + 1}:</span>
            <div class="flex gap-1 items-center">
                <input type="number" 
                       value="${Math.round(point.x)}" 
                       step="1" 
                       min="${minX}" 
                       max="${maxX}" 
                       class="w-10 h-6 text-sm border rounded px-1 text-center number-input" 
                       onchange="updatePointValue(${index}, 'x', this.value)">
                <span class="text-xs">°C →</span>
                <input type="number" 
                       value="${Math.round(point.y)}" 
                       step="1" 
                       min="${minY}" 
                       max="${maxY}" 
                       class="w-10 h-6 text-sm border rounded px-1 text-center number-input" 
                       onchange="updatePointValue(${index}, 'y', this.value)">
                <span class="text-xs">%</span>
                <button onclick="removePoint(${index})" 
                        class="ml-1 bg-red-400 hover:bg-red-500 text-white w-4 h-4 rounded text-xs flex items-center justify-center"
                        title="Remove this point">×</button>
            </div>
        </div>`;
    });
    
    infoEl.innerHTML = html;
}

// Functions to handle editable point manipulation
function updatePointValue(index, axis, value) {
    if (!fanCurves[activeCurve] || !fanCurves[activeCurve].data[index]) return;
    
    const numValue = parseInt(value);
    if (isNaN(numValue)) return;
    
    const curveData = fanCurves[activeCurve].data;
    
    // Apply the same constraints as drag operations
    let minX, maxX, minY, maxY;
    
    if (axis === 'x') {
        // Temperature constraints: must be between adjacent points or global limits
        minX = (index > 0) ? curveData[index - 1].x + 1 : MIN_TEMP;
        maxX = (index < curveData.length - 1) ? curveData[index + 1].x - 1 : MAX_TEMP;
        
        // Clamp the temperature value
        const constrainedValue = Math.max(minX, Math.min(maxX, numValue));
        fanCurves[activeCurve].data[index].x = constrainedValue;
    } else if (axis === 'y') {
        // Fan speed constraints: must be between adjacent points or global limits
        minY = (index > 0) ? curveData[index - 1].y : MIN_SPEED;
        maxY = (index < curveData.length - 1) ? curveData[index + 1].y : MAX_SPEED;
        
        // Clamp the fan speed value
        const constrainedValue = Math.max(minY, Math.min(maxY, numValue));
        fanCurves[activeCurve].data[index].y = constrainedValue;
    }
    
    // Sort points by temperature after update
    sortPointsByTemperature(fanCurves[activeCurve].data);
    
    // Refresh chart and display
    refreshChart();
    updatePointsDisplay();
    
    // Signal unsaved changes after manual value update
    if (window.updateUnsavedChangesStatus) {
        window.updateUnsavedChangesStatus(true);
    }
}

function addPoint() {
    if (!fanCurves[activeCurve]) return;
    
    const data = fanCurves[activeCurve].data;
    
    // Add new point at a reasonable temperature
    let newTemp = 50; // Default temperature
    if (data.length > 0) {
        // Add point 10°C higher than the highest existing point
        const maxTemp = Math.max(...data.map(p => p.x));
        newTemp = Math.min(100, maxTemp + 10);
    }
    
    // Calculate fan speed based on linear interpolation of existing points
    let newSpeed = 50; // Default speed
    if (data.length >= 2) {
        // Find appropriate speed by interpolating
        data.sort((a, b) => a.x - b.x);
        if (newTemp > data[data.length - 1].x) {
            // Extrapolate from last two points
            const p1 = data[data.length - 2];
            const p2 = data[data.length - 1];
            const slope = (p2.y - p1.y) / (p2.x - p1.x);
            newSpeed = Math.max(0, Math.min(100, p2.y + slope * (newTemp - p2.x)));
        } else {
            // Interpolate between existing points
            for (let i = 0; i < data.length - 1; i++) {
                if (newTemp >= data[i].x && newTemp <= data[i + 1].x) {
                    const ratio = (newTemp - data[i].x) / (data[i + 1].x - data[i].x);
                    newSpeed = data[i].y + ratio * (data[i + 1].y - data[i].y);
                    break;
                }
            }
        }
    }
    
    data.push({ x: newTemp, y: newSpeed });
    sortPointsByTemperature(data);
    
    refreshChart();
    updatePointsDisplay();
    
    // Signal unsaved changes after adding point
    if (window.updateUnsavedChangesStatus) {
        window.updateUnsavedChangesStatus(true);
    }
}

function removePoint(index) {
    if (!fanCurves[activeCurve] || fanCurves[activeCurve].data.length <= 2) {
        alert('Cannot remove point: minimum 2 points required for a curve');
        return;
    }
    
    fanCurves[activeCurve].data.splice(index, 1);
    
    refreshChart();
    updatePointsDisplay();
    
    // Signal unsaved changes after removing point
    if (window.updateUnsavedChangesStatus) {
        window.updateUnsavedChangesStatus(true);
    }
}

function removeLastPoint() {
    if (!fanCurves[activeCurve] || fanCurves[activeCurve].data.length <= 2) {
        alert('Cannot remove point: minimum 2 points required for a curve');
        return;
    }
    
    fanCurves[activeCurve].data.pop();
    
    refreshChart();
    updatePointsDisplay();
    
    // Signal unsaved changes after removing last point
    if (window.updateUnsavedChangesStatus) {
        window.updateUnsavedChangesStatus(true);
    }
}

function getCurveKeys() {
    return Object.keys(fanCurves); // Keep original insertion order, no sorting
}

function refreshChart() {
    if (!fanCurveChart) return;
    
    ensureVisibilitySettings();
    
    const curveKeys = getCurveKeys();
    const datasets = [];
    
    // Keep curves in their original order to prevent legend rearrangement
    // Just change the rendering order by adjusting z-index via borderWidth and other properties
    curveKeys.forEach((curveKey) => {
        const curveInfo = fanCurves[curveKey];
        if (!curveInfo) return;
        
        const style = getCurveStyle(curveInfo.colorIndex || 0);
        const isActive = curveKey === activeCurve;
        
        sortPointsByTemperature(curveInfo.data);
        
        const extendedCurve = generateExtendedCurve(curveInfo.data);
        
        // Line dataset
        datasets.push({
            label: curveInfo.name,
            data: extendedCurve,
            backgroundColor: style.curveFill,
            borderColor: isActive ? style.curveColor : style.curveColor.replace('0.8', '0.4'),
            borderWidth: isActive ? 5 : 3, // Make active curve thicker instead of reordering
            pointRadius: 0,
            showLine: true,
            tension: 0,
            fill: false,
            hidden: !curveVisibility[curveKey],
            curveKey: curveKey
        });
        
        // Points dataset
        datasets.push({
            label: curveInfo.name + ' Points',
            data: [...curveInfo.data],
            backgroundColor: style.pointColor,
            borderColor: style.pointBorder,
            borderWidth: 3,
            pointRadius: isActive ? 12 : 4, // Make active points much larger
            pointHoverRadius: isActive ? 15 : 8, // More reasonable hover radius
            showLine: false,
            hidden: !curveVisibility[curveKey],
            curveKey: curveKey
        });
    });
    
    // Update x-axis title to include active curve's sensor
    const activeCurveInfo = fanCurves[activeCurve];
    const sensorText = activeCurveInfo?.sensor && activeCurveInfo.sensor !== 'None' 
        ? ` (${activeCurveInfo.sensor})` 
        : '';
    fanCurveChart.options.scales.x.title.text = `Temperature (°C)${sensorText}`;
    
    // Update chart title with profile name
    if (activeProfileName) {
        fanCurveChart.options.plugins.title.text = `${activeProfileName}`;
    }
    
    fanCurveChart.data.datasets = datasets;
    fanCurveChart.update('none');
    updatePointsDisplay();
}

function addPointAtCoordinates(temperature, fanSpeed) {
    const temp = Math.round(constrainValue(temperature, MIN_TEMP, MAX_TEMP));
    const speed = Math.round(constrainValue(fanSpeed, MIN_SPEED, MAX_SPEED));
    
    const activeData = fanCurves[activeCurve];
    if (!activeData) return false;
    
    const nearbyPoint = activeData.data.find(p => Math.abs(p.x - temp) < 3);
    if (nearbyPoint) return false;

    activeData.data.push({x: temp, y: speed});
    refreshChart();
    
    // Signal unsaved changes after adding point at coordinates
    if (window.updateUnsavedChangesStatus) {
        window.updateUnsavedChangesStatus(true);
    }
    
    return true;
}

function removePointAtIndex(index, curveKey) {
    const curveInfo = fanCurves[curveKey];
    if (!curveInfo || curveInfo.data.length <= MIN_POINTS) return false;
    
    curveInfo.data.splice(index, 1);
    refreshChart();
    
    // Signal unsaved changes after removing point at index
    if (window.updateUnsavedChangesStatus) {
        window.updateUnsavedChangesStatus(true);
    }
    
    return true;
}

function handleChartClick(event) {
    if (!fanCurveChart) return;
    
    // Hide add point tooltip when clicking
    hideAddPointTooltip();
    
    const elements = fanCurveChart.getElementsAtEventForMode(event, 'nearest', {intersect: true}, true);
    if (elements.length > 0 && fanCurveChart.data.datasets[elements[0].datasetIndex].label.includes('Points')) {
        return;
    }
    
    const canvasPosition = Chart.helpers.getRelativePosition(event, fanCurveChart);
    const temperature = fanCurveChart.scales.x.getValueForPixel(canvasPosition.x);
    const fanSpeed = fanCurveChart.scales.y.getValueForPixel(canvasPosition.y);
    
    if (isClickNearCurve(temperature, fanSpeed, activeCurve)) {
        const interpolatedSpeed = interpolateFanSpeed(temperature, activeCurve);
        if (interpolatedSpeed !== null) {
            addPointAtCoordinates(temperature, interpolatedSpeed);
        }
    }
}

function handleRightClick(event) {
    event.preventDefault();
    if (!fanCurveChart) return;
    
    const elements = fanCurveChart.getElementsAtEventForMode(event, 'nearest', {intersect: true}, true);
    if (elements.length > 0) {
        const element = elements[0];
        const originalDataset = fanCurveChart.data.datasets[element.datasetIndex];
        
        if (originalDataset.label.includes('Points')) {
            const curveKey = originalDataset.curveKey;
            
            // Check if we're already on the active curve
            if (curveKey === activeCurve) {
                removePointAtIndex(element.index, curveKey);
                return;
            }
            
            // Use the same detection logic as onDragStart to find the active curve point
            let nearbyElements = fanCurveChart.getElementsAtEventForMode(
                event, 
                'nearest', 
                { intersect: false },
                true
            );

            if (nearbyElements.length === 0) {
                nearbyElements = fanCurveChart.getElementsAtEventForMode(
                    event, 
                    'nearest', 
                    { intersect: false, includeInvisible: false }, 
                    false
                );
            }

            // Look for an active curve point among all nearby elements
            const activePoint = nearbyElements.find(elem => {
                const dataset = fanCurveChart.data.datasets[elem.datasetIndex];
                return dataset.label.includes('Points') && dataset.curveKey === activeCurve;
            });

            if (activePoint) {
                // Check if we're at the same coordinates as the active point
                const originalPoint = originalDataset.data[element.index];
                const activePointData = fanCurveChart.data.datasets[activePoint.datasetIndex].data[activePoint.index];
                
                if (originalPoint && activePointData && 
                    Math.abs(originalPoint.x - activePointData.x) < 0.5 && 
                    Math.abs(originalPoint.y - activePointData.y) < 1) {
                    
                    // Points are at same coordinates, delete the active curve point
                    removePointAtIndex(activePoint.index, activeCurve);
                    return;
                }
            }
        }
    }
}

function initializeChart() {
    const canvas = document.getElementById('fanCurveChart');
    if (!canvas) return false;
    
    if (fanCurveChart) fanCurveChart.destroy();
    
    const ctx = canvas.getContext('2d');
    fanCurveChart = new Chart(ctx, {
        type: 'scatter',
        data: { datasets: [] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: { 
                intersect: true, // Changed to true so tooltip only shows when directly over points
                mode: 'point', // Changed to point mode for precise hovering
                axis: 'xy',
                includeInvisible: false
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Multi-Curve Fan Control',
                    font: {size: 16, weight: 'bold'},
                    padding: 20,
                    color: '#ffffff' // White for dark theme
                },
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        filter: (item) => !item.text.includes('Points'),
                        color: '#ffffff' // White for dark theme
                    },
                    onHover: (evt, legendItem, legend) => {
                        const index = legendItem.datasetIndex;
                        const ci = legend.chart;
                        const curveKey = ci.data.datasets[index].curveKey;
                        
                        if (curveKey) {
                            const curveName = fanCurves[curveKey]?.name || curveKey;
                            const isVisible = curveVisibility[curveKey];
                            
                            let tooltipText;
                            if (curveKey === activeCurve) {
                                // Don't set pointer cursor for active curve since it can't be clicked
                                evt.native.target.style.cursor = 'default';
                                tooltipText = `${curveName} (Active curve - cannot be hidden)`;
                            } else {
                                // Set pointer cursor only for non-active curves that can be clicked
                                evt.native.target.style.cursor = 'pointer';
                                const action = isVisible ? 'Hide' : 'Show';
                                tooltipText = `${action} ${curveName}`;
                            }
                            
                            // Create custom tooltip and start following cursor
                            showCustomTooltip(evt, tooltipText);
                            startTooltipFollowing(evt.native.target);
                        }
                    },
                    onLeave: (evt, legendItem, legend) => {
                        // Reset cursor when leaving legend items
                        evt.native.target.style.cursor = 'default';
                        
                        // Stop following cursor and hide custom tooltip
                        stopTooltipFollowing();
                        hideCustomTooltip();
                    },
                    onClick: (e, legendItem, legend) => {
                        const index = legendItem.datasetIndex;
                        const ci = legend.chart;
                        const meta = ci.getDatasetMeta(index);
                        
                        const curveKey = ci.data.datasets[index].curveKey;
                        
                        // Prevent the active curve from being toggled invisible
                        if (curveKey === activeCurve) {
                            console.log(`Cannot hide active curve: ${curveKey}`);
                            return; // Exit early, don't toggle visibility
                        }
                        
                        const newHiddenState = meta.hidden === null ? !ci.data.datasets[index].hidden : !meta.hidden;
                        meta.hidden = newHiddenState;

                        const pointsDatasetIndex = index + 1;
                        if (pointsDatasetIndex < ci.data.datasets.length) {
                            const pointsMeta = ci.getDatasetMeta(pointsDatasetIndex);
                            pointsMeta.hidden = newHiddenState;
                        }

                        if (curveKey) {
                            curveVisibility[curveKey] = !newHiddenState;
                            
                            // Update tooltip text to reflect new state
                            updateTooltipText(curveKey);
                        }
                        
                        ci.update();
                    }
                },
                tooltip: {
                    displayColors: false,
                    mode: 'point', // Only show tooltip when directly over a point
                    intersect: true, // Must intersect with the point, not just be nearby
                    position: 'average', // Centers tooltip above the point
                    backgroundColor: 'rgba(17, 24, 39, 0.95)', // Dark gray background
                    titleColor: '#ffffff', // White text
                    bodyColor: '#ffffff', // White text
                    borderColor: '#ffffff', // White border
                    borderWidth: 1,
                    cornerRadius: 6,
                    padding: 8,
                    yAlign: 'bottom', // Position tooltip above the point
                    callbacks: {
                        label: function(context) {
                            const dataset = context.chart.data.datasets[context.datasetIndex];
                            if (dataset.label.includes('Points')) {
                                const curveKey = dataset.curveKey;
                                const curveName = fanCurves[curveKey]?.name || curveKey;
                                return `${curveName}: ${context.parsed.x}°C → ${context.parsed.y}%`;
                            }
                            return '';
                        }
                    }
                },
                dragData: {
                    round: 0, // Round to whole numbers
                    dragX: true,
                    onDragStart: function(e, datasetIndex, index, value) {
                        console.log(`=== DRAG START DEBUG ===`);
                        console.log(`Drag attempt on dataset: ${datasetIndex}, index: ${index}`);
                        
                        const originalDataset = fanCurveChart.data.datasets[datasetIndex];
                        console.log(`Original dataset label: ${originalDataset.label}`);
                        console.log(`Original dataset curveKey: ${originalDataset.curveKey}`);
                        console.log(`Active curve: ${activeCurve}`);
                        
                        // Check if we're already on the active curve and it's a points dataset
                        if (originalDataset.curveKey === activeCurve && originalDataset.label.includes('Points')) {
                            console.log(`Active curve point detected, allowing drag`);
                            return true;
                        }
                        
                        // Use the same detection logic as hover to find the active curve point
                        let nearbyElements = fanCurveChart.getElementsAtEventForMode(
                            e, 
                            'nearest', 
                            { intersect: false },
                            true
                        );

                        if (nearbyElements.length === 0) {
                            nearbyElements = fanCurveChart.getElementsAtEventForMode(
                                e, 
                                'nearest', 
                                { intersect: false, includeInvisible: false }, 
                                false
                            );
                        }

                        // Look for an active curve point among all nearby elements
                        const activePoint = nearbyElements.find(element => {
                            const dataset = fanCurveChart.data.datasets[element.datasetIndex];
                            return dataset.label.includes('Points') && dataset.curveKey === activeCurve;
                        });

                        if (activePoint) {
                            console.log(`Active point found - dataset: ${activePoint.datasetIndex}, index: ${activePoint.index}`);
                            
                            // Check if we're at the same coordinates as the active point
                            const originalPoint = originalDataset.data[index];
                            const activePointData = fanCurveChart.data.datasets[activePoint.datasetIndex].data[activePoint.index];
                            
                            if (originalPoint && activePointData && 
                                Math.abs(originalPoint.x - activePointData.x) < 0.5 && 
                                Math.abs(originalPoint.y - activePointData.y) < 1) {
                                
                                console.log(`Points are at same coordinates, temporarily allowing drag`);
                                
                                // Store the active point info for use in onDrag
                                fanCurveChart._activeDragTarget = {
                                    datasetIndex: activePoint.datasetIndex,
                                    index: activePoint.index,
                                    curveKey: activeCurve
                                };
                                
                                return true; // Allow the drag to start
                            }
                        }
                        
                        console.log(`No valid active curve point for dragging, preventing drag`);
                        return false;
                    },
                    onDrag: function(e, datasetIndex, index, value) {
                        console.log(`=== DRAG ACTIVE ===`);
                        console.log(`Dragging dataset: ${datasetIndex}, index: ${index}`);
                        
                        // Check if we have a stored active drag target (for overlapping points)
                        if (fanCurveChart._activeDragTarget) {
                            console.log(`Using stored active drag target`);
                            const target = fanCurveChart._activeDragTarget;
                            console.log(`Target: dataset ${target.datasetIndex}, index ${target.index}, curve ${target.curveKey}`);
                            
                            // Use the active curve data instead
                            const curveData = fanCurves[target.curveKey].data;
                            const activeIndex = target.index;
                            
                            const minX = (activeIndex > 0) ? curveData[activeIndex - 1].x + 1 : MIN_TEMP;
                            const maxX = (activeIndex < curveData.length - 1) ? curveData[activeIndex + 1].x - 1 : MAX_TEMP;
                            
                            const minY = (activeIndex > 0) ? curveData[activeIndex - 1].y : MIN_SPEED;
                            const maxY = (activeIndex < curveData.length - 1) ? curveData[activeIndex + 1].y : MAX_SPEED;

                            value.x = constrainValue(value.x, minX, maxX);
                            value.y = constrainValue(value.y, minY, maxY);

                            // Update ONLY the active curve data - don't touch the original dataset
                            curveData[activeIndex] = {x: value.x, y: value.y};
                            
                            // Update the active curve's datasets directly
                            fanCurveChart.data.datasets[target.datasetIndex].data[activeIndex] = {x: value.x, y: value.y};
                            
                            const lineDatasetIndex = fanCurveChart.data.datasets.findIndex(d => d.curveKey === target.curveKey && !d.label.includes('Points'));
                            if (lineDatasetIndex !== -1) {
                                fanCurveChart.data.datasets[lineDatasetIndex].data = generateExtendedCurve(curveData);
                            }
                            
                            fanCurveChart.update('none'); 
                            updatePointsDisplay();
                            console.log(`Active curve drag successful, point updated to: x=${value.x}, y=${value.y}`);
                            
                            // Prevent the plugin from processing the original drag
                            return false;
                        }
                        
                        // Normal drag handling (when no override needed)
                        const dataset = fanCurveChart.data.datasets[datasetIndex];
                        if (!dataset.label.includes('Points')) {
                            console.log(`Not a points dataset, canceling drag`);
                            return false;
                        }

                        const curveKey = dataset.curveKey;
                        console.log(`Curve key: ${curveKey}, Active curve: ${activeCurve}`);
                        
                        if (curveKey !== activeCurve) {
                            console.log(`Curve key doesn't match active curve, canceling drag`);
                            return false;
                        }
                        
                        const curveData = fanCurves[curveKey].data;

                        const minX = (index > 0) ? curveData[index - 1].x + 1 : MIN_TEMP;
                        const maxX = (index < curveData.length - 1) ? curveData[index + 1].x - 1 : MAX_TEMP;
                        
                        const minY = (index > 0) ? curveData[index - 1].y : MIN_SPEED;
                        const maxY = (index < curveData.length - 1) ? curveData[index + 1].y : MAX_SPEED;

                        value.x = constrainValue(value.x, minX, maxX);
                        value.y = constrainValue(value.y, minY, maxY);

                        curveData[index] = {x: value.x, y: value.y};
                        
                        const lineDatasetIndex = fanCurveChart.data.datasets.findIndex(d => d.curveKey === curveKey && !d.label.includes('Points'));
                        if (lineDatasetIndex !== -1) {
                            fanCurveChart.data.datasets[lineDatasetIndex].data = generateExtendedCurve(curveData);
                        }
                        
                        fanCurveChart.update('none'); 
                        updatePointsDisplay();
                        console.log(`Normal drag successful, point updated to: x=${value.x}, y=${value.y}`);
                        return true;
                    },
                    onDragEnd: function(e, datasetIndex, index, value) {
                        // Check if we used the stored active drag target
                        if (fanCurveChart._activeDragTarget) {
                            console.log(`Clearing stored active drag target - no additional processing needed`);
                            const target = fanCurveChart._activeDragTarget;
                            
                            // Round the final values in the active curve data
                            const curveData = fanCurves[target.curveKey].data;
                            curveData[target.index].x = Math.round(curveData[target.index].x);
                            curveData[target.index].y = Math.round(curveData[target.index].y);
                            
                            // Clear the target and refresh
                            fanCurveChart._activeDragTarget = null;
                            refreshChart();
                            
                            // Signal unsaved changes after drag end
                            if (window.updateUnsavedChangesStatus) {
                                window.updateUnsavedChangesStatus(true);
                            }
                            
                            return true;
                        }
                        
                        // Normal drag end processing (when no override was used)
                        const curveKey = fanCurveChart.data.datasets[datasetIndex].curveKey;
                        value.x = Math.round(value.x);
                        value.y = Math.round(value.y);
                        fanCurves[curveKey].data[index] = {x: value.x, y: value.y};
                        refreshChart();
                        
                        // Signal unsaved changes after drag end
                        if (window.updateUnsavedChangesStatus) {
                            window.updateUnsavedChangesStatus(true);
                        }
                        
                        return true;
                    }
                }
            },
            scales: {
                x: {
                    type: 'linear',
                    title: { 
                        display: true, 
                        text: 'Temperature (°C)', 
                        font: {size: 14, weight: 'bold'},
                        color: '#ffffff' // White for dark theme
                    },
                    min: MIN_TEMP, max: MAX_TEMP,
                    ticks: { 
                        stepSize: 10, 
                        callback: (v) => v + '°C',
                        color: '#ffffff' // White text
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.2)' // White grid lines with opacity
                    }
                },
                y: {
                    type: 'linear',
                    title: { 
                        display: true, 
                        text: 'Fan Speed (%)', 
                        font: {size: 14, weight: 'bold'},
                        color: '#ffffff' // White for dark theme
                    },
                    min: MIN_SPEED, 
                    max: MAX_SPEED + 10, // Add 10% headroom
                    ticks: { 
                        stepSize: 10,
                        callback: (v) => v <= 100 ? v + '%' : '', // Only show labels up to 100%
                        max: 100, // This ensures grid lines stop at 100%
                        color: '#ffffff' // White text
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.2)' // White grid lines with opacity
                    }
                }
            },
            onClick: handleChartClick,
            onHover: function(event, elements) {
                const target = event.native.target;
                
                // Check if we're currently hovering over a legend item - if so, don't override cursor
                // Legend items may have 'pointer' (for clickable items) or 'default' (for active curve)
                if (target.style.cursor === 'pointer' || 
                    (target.style.cursor === 'default' && target.closest('.chartjs-legend'))) {
                    return; // Legend is handling cursor, don't interfere
                }
                
                // First, check if we're hovering directly over an active curve point for drag cursor
                let nearbyElements = fanCurveChart.getElementsAtEventForMode(
                    event, 
                    'nearest', 
                    { intersect: true }, // Use intersect: true for more precise point detection
                    true
                );

                // Look for an active curve point that we're directly over
                const activePoint = nearbyElements.find(element => {
                    const dataset = fanCurveChart.data.datasets[element.datasetIndex];
                    return dataset.label.includes('Points') && dataset.curveKey === activeCurve;
                });

                if (activePoint) {
                    target.style.cursor = 'grab';
                    hideAddPointTooltip(); // Hide add point tooltip when over a point
                    return;
                }
                
                // If no direct point hit, check if we're near the active curve line for adding points (crosshair cursor)
                const pos = Chart.helpers.getRelativePosition(event, fanCurveChart);
                const temp = fanCurveChart.scales.x.getValueForPixel(pos.x);
                const speed = fanCurveChart.scales.y.getValueForPixel(pos.y);
                
                if (isClickNearCurve(temp, speed, activeCurve)) {
                    target.style.cursor = 'crosshair';
                    
                    // Show tooltip with the coordinates of the point that would be added
                    const interpolatedSpeed = interpolateFanSpeed(temp, activeCurve);
                    if (interpolatedSpeed !== null) {
                        const tooltipText = `Add point at ${Math.round(temp)}°C → ${Math.round(interpolatedSpeed)}%`;
                        showAddPointTooltip(event, tooltipText);
                    }
                    return;
                }
                
                // Default cursor for all other areas
                target.style.cursor = 'default';
                hideAddPointTooltip(); // Hide tooltip when not over a line
            }
        }
    });
    canvas.addEventListener('contextmenu', handleRightClick);
    
    // Add mouse leave event to hide add point tooltip
    canvas.addEventListener('mouseleave', function() {
        hideAddPointTooltip();
    });
    
    refreshChart();
    // Emit event to signal Python that the chart is ready
    emitEvent('fan_curve_ready');
    return true;
}

function addNewCurve(id, sensor = 'None') {
    const curveId = `${id}`;
    // Find first unused color index
    const usedColors = new Set(Object.values(fanCurves).map(curve => curve.colorIndex));
    let colorIndex = 0;
    while (usedColors.has(colorIndex)) colorIndex++;
    
    fanCurves[`${id}`] = {
        name: `${id}`,
        sensor: sensor, // Use provided sensor or default
        colorIndex: colorIndex, // Store the color index
        data: [{"x": 30, "y": 50}, {"x": 40, "y": 60}, {"x": 50, "y": 70}, {"x": 60, "y": 80}, {"x": 70, "y": 90}, {"x": 80, "y": 100}]
    };
    curveVisibility[curveId] = true;
    activeCurve = curveId;
    refreshChart();
}

function removeActiveCurve() {
    const curveKeys = getCurveKeys();
    if (curveKeys.length <= 1) {
        return;
    }
    const removedName = fanCurves[activeCurve].name;
    delete fanCurves[activeCurve];
    delete curveVisibility[activeCurve];
    activeCurve = getCurveKeys()[0];
    refreshChart();
}

function resetActiveCurve() {
    fanCurves[activeCurve].data = [{"x": 30, "y": 20}, {"x": 40, "y": 30}, {"x": 50, "y": 45}, {"x": 60, "y": 65}, {"x": 70, "y": 80}, {"x": 80, "y": 100}];
    refreshChart();
}

function resetAllCurves() {
    Object.keys(fanCurves).forEach(curveKey => {
        fanCurves[curveKey].data = [{"x": 30, "y": 20}, {"x": 40, "y": 30}, {"x": 50, "y": 45}, {"x": 60, "y": 65}, {"x": 70, "y": 80}, {"x": 80, "y": 100}];
    });
    refreshChart();
}

function clearAllCurves() {
    fanCurves = {};
    curveVisibility = {};
    activeCurve = '';
    if (fanCurveChart) {
        fanCurveChart.data.datasets = [];
        fanCurveChart.update('none');
    }
    updatePointsDisplay();
}

function loadProfileData(profileData, activeProfileCurve, profileName) {
    // Clear existing data without updating chart
    fanCurves = {};
    curveVisibility = {};
    activeCurve = '';
    activeProfileName = profileName || '';
    
    // Find first unused color index for each curve
    let colorIndex = 0;
    
    // Load all curves at once
    for (const [curveName, curveInfo] of Object.entries(profileData)) {
        const curveId = curveName;
        
        fanCurves[curveId] = {
            name: curveName,
            sensor: curveInfo.sensor || 'None',
            colorIndex: colorIndex,
            data: [...curveInfo.data] // Make a copy of the data
        };
        curveVisibility[curveId] = true;
        colorIndex++;
    }
    
    // Set active curve
    if (activeProfileCurve && fanCurves[activeProfileCurve]) {
        activeCurve = activeProfileCurve;
    } else if (Object.keys(fanCurves).length > 0) {
        activeCurve = Object.keys(fanCurves)[0];
    }
    
    // Single chart update for all changes - this prevents flickering
    if (fanCurveChart) {
        ensureVisibilitySettings();
        
        const curveKeys = getCurveKeys();
        const datasets = [];
        
        // Build all datasets at once
        curveKeys.forEach((curveKey) => {
            const curveInfo = fanCurves[curveKey];
            if (!curveInfo) return;
            
            const style = getCurveStyle(curveInfo.colorIndex || 0);
            const isActive = curveKey === activeCurve;
            
            sortPointsByTemperature(curveInfo.data);
            
            const extendedCurve = generateExtendedCurve(curveInfo.data);
            
            // Line dataset
            datasets.push({
                label: curveInfo.name,
                data: extendedCurve,
                backgroundColor: style.curveFill,
                borderColor: isActive ? style.curveColor : style.curveColor.replace('0.8', '0.4'),
                borderWidth: isActive ? 5 : 3,
                pointRadius: 0,
                showLine: true,
                tension: 0,
                fill: false,
                hidden: !curveVisibility[curveKey],
                curveKey: curveKey
            });
            
            // Points dataset
            datasets.push({
                label: curveInfo.name + ' Points',
                data: [...curveInfo.data],
                backgroundColor: style.pointColor,
                borderColor: style.pointBorder,
                borderWidth: 3,
                pointRadius: isActive ? 12 : 4,
                pointHoverRadius: isActive ? 15 : 8,
                showLine: false,
                hidden: !curveVisibility[curveKey],
                curveKey: curveKey
            });
        });
        
        // Update x-axis title
        const activeCurveInfo = fanCurves[activeCurve];
        const sensorText = activeCurveInfo?.sensor && activeCurveInfo.sensor !== 'None' 
            ? ` (${activeCurveInfo.sensor})` 
            : '';
        fanCurveChart.options.scales.x.title.text = `Temperature (°C)${sensorText}`;
        
        // Update chart title with profile name
        if (profileName) {
            fanCurveChart.options.plugins.title.text = `${profileName}`;
        }
        
        // Single update with all new data
        fanCurveChart.data.datasets = datasets;
        fanCurveChart.update('none');
        updatePointsDisplay();
    }
}

function getCurrentDataForPython() {
    Object.values(fanCurves).forEach(curveInfo => sortPointsByTemperature(curveInfo.data));
    
    const result = JSON.stringify({
        curves: fanCurves,
        activeCurve: activeCurve,
        visibility: curveVisibility
    });
    
    return result;
}

function getCurrentState() {
    if (!fanCurveChart) return {curves: {}, active: null, visibility: {}};
    return {curves: fanCurves, active: activeCurve, visibility: curveVisibility};
}

function setActiveCurve(curveKey) {
    if (fanCurves[curveKey]) {
        activeCurve = curveKey;
        
        // If the curve is not visible, make it visible when selected as active
        if (curveVisibility[curveKey] === false) {
            curveVisibility[curveKey] = true;
            console.log(`Making curve ${curveKey} visible as it was selected as active`);
        }
        
        refreshChart();
    }
}

function updateCurveName(curveKey, newName) {
    if (fanCurves[curveKey]) {
        fanCurves[curveKey].name = newName;
        fanCurves[newName] = fanCurves[curveKey]
        delete fanCurves[curveKey]
        refreshChart();
    }
}

function updateCurveSensor(curveKey, newSensor) {
    if (fanCurves[curveKey]) {
        fanCurves[curveKey].sensor = newSensor;
        refreshChart(); // Refresh chart to update the axis label with new sensor
        
        // Signal unsaved changes after sensor update
        if (window.updateUnsavedChangesStatus) {
            window.updateUnsavedChangesStatus(true);
        }
    }
}

// Custom tooltip functions for legend hover
let tooltipFollowHandler = null;

function showCustomTooltip(event, text) {
    // Remove any existing tooltip
    hideCustomTooltip();
    
    // Create tooltip element
    const tooltip = document.createElement('div');
    tooltip.id = 'legend-custom-tooltip';
    tooltip.style.cssText = `
        position: fixed;
        background: rgba(0, 0, 0, 0.8);
        color: white;
        padding: 4px 6px;
        border-radius: 5px;
        font-size: 13px;
        white-space: nowrap;
        z-index: 1000;
        pointer-events: none;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        font-family: inherit;
        transition: opacity 0.2s ease;
    `;
    tooltip.textContent = text;
    
    // Add to document
    document.body.appendChild(tooltip);
    
    // Position tooltip near mouse cursor
    updateTooltipPosition(event.native.clientX, event.native.clientY);
}

function updateTooltipPosition(clientX, clientY) {
    const tooltip = document.getElementById('legend-custom-tooltip');
    if (!tooltip) return;
    
    const rect = tooltip.getBoundingClientRect();
    
    // Center horizontally above the cursor
    let left = clientX - (rect.width / 2);
    let top = clientY - rect.height - 10;
    
    // Ensure tooltip stays within screen bounds
    const margin = 5;
    left = Math.max(margin, Math.min(left, window.innerWidth - rect.width - margin));
    
    // If tooltip would go above screen, position below the cursor
    if (top < margin) {
        top = clientY + 10;
    }
    
    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
}

function startTooltipFollowing(targetElement) {
    // Remove any existing handler
    stopTooltipFollowing();
    
    // Create new handler for tooltip following
    tooltipFollowHandler = function(e) {
        updateTooltipPosition(e.clientX, e.clientY);
        // Note: Cursor management is now handled by legend onHover/onLeave to avoid conflicts
    };
    
    // Add mousemove listener to the target element
    targetElement.addEventListener('mousemove', tooltipFollowHandler);
}

function stopTooltipFollowing() {
    if (tooltipFollowHandler) {
        // Remove the event listener from all potential target elements
        // Since we don't know which element it was attached to, we'll remove it from document
        document.removeEventListener('mousemove', tooltipFollowHandler);
        
        // Also try to remove from the legend area specifically
        const legend = document.querySelector('canvas').parentElement.querySelector('.chartjs-legend');
        if (legend) {
            legend.removeEventListener('mousemove', tooltipFollowHandler);
        }
        
        tooltipFollowHandler = null;
    }
}

function hideCustomTooltip() {
    const tooltip = document.getElementById('legend-custom-tooltip');
    if (tooltip) {
        tooltip.remove();
    }
}

function updateTooltipText(curveKey) {
    const tooltip = document.getElementById('legend-custom-tooltip');
    if (!tooltip) return;
    
    const curveName = fanCurves[curveKey]?.name || curveKey;
    const isVisible = curveVisibility[curveKey];
    
    let tooltipText;
    if (curveKey === activeCurve) {
        tooltipText = `${curveName} (Active curve - cannot be hidden)`;
    } else {
        const action = isVisible ? 'Hide' : 'Show';
        tooltipText = `${action} ${curveName}`;
    }
    
    tooltip.textContent = tooltipText;
}

// Add point tooltip functions
function showAddPointTooltip(event, text) {
    // Remove any existing add point tooltip
    hideAddPointTooltip();
    
    // Create tooltip element
    const tooltip = document.createElement('div');
    tooltip.id = 'add-point-tooltip';
    tooltip.style.cssText = `
        position: fixed;
        background: rgba(34, 197, 94, 0.9);
        color: white;
        padding: 4px 6px;
        border-radius: 5px;
        font-size: 13px;
        white-space: nowrap;
        z-index: 1001;
        pointer-events: none;
        box-shadow: 0 2px 8px rgba(34, 197, 94, 0.3);
        font-family: inherit;
        transition: opacity 0.2s ease;
    `;
    tooltip.textContent = text;
    
    // Add to document
    document.body.appendChild(tooltip);
    
    // Position tooltip near mouse cursor
    updateAddPointTooltipPosition(event.native.clientX, event.native.clientY);
}

function updateAddPointTooltipPosition(clientX, clientY) {
    const tooltip = document.getElementById('add-point-tooltip');
    if (!tooltip) return;
    
    const rect = tooltip.getBoundingClientRect();
    
    // Center horizontally above the cursor
    let left = clientX - (rect.width / 2);
    let top = clientY - rect.height - 10;
    
    // Ensure tooltip stays within screen bounds
    const margin = 5;
    left = Math.max(margin, Math.min(left, window.innerWidth - rect.width - margin));
    
    // If tooltip would go above screen, position below the cursor
    if (top < margin) {
        top = clientY + 10;
    }
    
    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
}

function hideAddPointTooltip() {
    const tooltip = document.getElementById('add-point-tooltip');
    if (tooltip) {
        tooltip.remove();
    }
}

// This is the main entry point for the JS initialization
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeChart);
} else {
    initializeChart();
}

// Global function exports for buttons/Python
window.resetActiveCurve = resetActiveCurve;
window.resetAllCurves = resetAllCurves;
window.clearAllCurves = clearAllCurves;
window.loadProfileData = loadProfileData;
window.getCurrentDataForPython = getCurrentDataForPython;
window.setActiveCurve = setActiveCurve;
window.addNewCurve = addNewCurve;
window.removeActiveCurve = removeActiveCurve;
window.updateCurveName = updateCurveName;
window.updateCurveSensor = updateCurveSensor;
window.getCurrentState = getCurrentState;

// Global variable to track unsaved changes status from Python
let pythonUnsavedChanges = false;

// Function to emit events to Python (for communication with NiceGUI backend)
function emitEvent(eventName, data = null) {
    try {
        if (window.emitEvent) {
            window.emitEvent(eventName, data);
        } else {
            console.log(`Event emitted: ${eventName}`, data);
        }
    } catch (error) {
        console.error(`Failed to emit event ${eventName}:`, error);
    }
}

// Function to update the unsaved changes status from Python
function updateUnsavedChangesStatus(hasChanges) {
    pythonUnsavedChanges = hasChanges;
}

// Function to check unsaved changes status from Python when needed
function checkUnsavedChangesFromPython() {
    try {
        emitEvent('check_unsaved_changes');
    } catch (error) {
        console.error('Error checking unsaved changes from Python:', error);
    }
}

// Note: Removed automatic polling - unsaved changes are now managed by explicit events
// from Python when structural changes occur or data is modified

// Beforeunload event handler to prompt user about unsaved changes
window.addEventListener('beforeunload', function(event) {
    if (pythonUnsavedChanges) {
        // Prevent the default behavior to show the browser's confirmation dialog
        event.preventDefault();
        
        // Set return value for older browsers
        event.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
        
        // Return the message for maximum compatibility
        return 'You have unsaved changes. Are you sure you want to leave?';
    }
    
    // Allow navigation if no unsaved changes
    return undefined;
});

// Function to update chart title (called from Python when profile is renamed)
function updateChartTitle(newTitle) {
    if (fanCurveChart && fanCurveChart.options && fanCurveChart.options.plugins && fanCurveChart.options.plugins.title) {
        fanCurveChart.options.plugins.title.text = newTitle;
        fanCurveChart.update('none'); // Update without animation for smooth title change
    }
}

// Export the update function for Python to call
window.updateUnsavedChangesStatus = updateUnsavedChangesStatus;
window.updateChartTitle = updateChartTitle;