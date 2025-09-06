document.addEventListener('DOMContentLoaded', () => {
    const viewBtn = document.getElementById('viewBtn');
    const batchSelect = document.getElementById('batch');
    const timetableSection = document.getElementById('timetable-section');

    viewBtn.addEventListener('click', () => {
        const batchId = batchSelect.value;
        if(!batchId) {
            alert('Please select a batch.');
            return;
        }

        // Fetch timetable from backend (here we mock with sample data)
        const timetable = getMockTimetable(batchId);
        renderTimetable(timetable);
    });

    function getMockTimetable(batchId) {
        // Replace with actual API call to backend
        return [
            {day:'Monday', period1:'Maths', period2:'Physics', period3:'EVS', period4:'Web Dev'},
            {day:'Tuesday', period1:'Graphics', period2:'Maths', period3:'EVS', period4:'Physics'},
            {day:'Wednesday', period1:'Web Dev', period2:'Physics', period3:'Maths', period4:'EVS'},
            {day:'Thursday', period1:'Maths', period2:'Graphics', period3:'EVS', period4:'Physics'},
            {day:'Friday', period1:'Physics', period2:'Maths', period3:'Web Dev', period4:'EVS'},
        ];
    }

    function renderTimetable(timetable) {
        let html = '<table><tr><th>Day</th><th>Period 1</th><th>Period 2</th><th>Period 3</th><th>Period 4</th></tr>';
        timetable.forEach(row => {
            html += `<tr>
                <td>${row.day}</td>
                <td>${row.period1}</td>
                <td>${row.period2}</td>
                <td>${row.period3}</td>
                <td>${row.period4}</td>
            </tr>`;
        });
        html += '</table>';
        timetableSection.innerHTML = html;
    }
});
