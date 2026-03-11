// Breeding Selection System JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const ramCards = document.querySelectorAll('.ram-card');
    const selectEweButtons = document.querySelectorAll('.select-ewe-btn');
    const modal = document.getElementById('breedingModal');
    const closeModal = document.querySelector('.close');
    const breedingForm = document.getElementById('breedingForm');
    const startDateInput = document.getElementById('startDate');
    const endDateSpan = document.getElementById('endDate');
    const expectedBirthSpan = document.getElementById('expectedBirth');
    
    let selectedEweId = '';
    let selectedRamId = '';

    // Set minimum date to today
    const today = new Date().toISOString().split('T')[0];
    startDateInput.min = today;

    // Ram selection
    ramCards.forEach(card => {
        card.addEventListener('click', function() {
            const ramId = this.getAttribute('data-ram-id');
            window.location.href = `?ram_id=${ramId}`;
        });
    });

    // // Ewe selection for breeding
    // selectEweButtons.forEach(button => {
    //     button.addEventListener('click', function() {
    //         selectedEweId = this.getAttribute('data-ewe-id');
    //         selectedRamId = this.getAttribute('data-ram-id');
            
    //         document.getElementById('selectedEweId').textContent = selectedEweId;
    //         document.getElementById('selectedRamId').textContent = selectedRamId;
            
    //         // Reset and show modal
    //         startDateInput.value = today;
    //         calculateDates();
    //         modal.style.display = 'block';
    //     });
    // });
    // Update the ewe selection to pass breed information
selectEweButtons.forEach(button => {
    button.addEventListener('click', function() {
        selectedEweId = this.getAttribute('data-ewe-id');
        selectedRamId = this.getAttribute('data-ram-id');
        const eweBreed = this.getAttribute('data-ewe-breed');
        const ramBreed = this.getAttribute('data-ram-breed');
        
        document.getElementById('selectedEweId').textContent = selectedEweId;
        document.getElementById('selectedRamId').textContent = selectedRamId;
        
        // Update breed prediction
        updateBreedPrediction(eweBreed, ramBreed);
        
        // Reset and show modal
        startDateInput.value = today;
        calculateDates();
        breedingModal.show();
    });
});

    // Date calculation
    startDateInput.addEventListener('change', calculateDates);

    function calculateDates() {
        const startDate = new Date(startDateInput.value);
        if (isNaN(startDate.getTime())) return;

        // End date: start date + 51 days
        const endDate = new Date(startDate);
        endDate.setDate(endDate.getDate() + 51);
        
        // Expected birth: start date + 155 days
        const expectedBirth = new Date(startDate);
        expectedBirth.setDate(expectedBirth.getDate() + 155);

        endDateSpan.textContent = endDate.toLocaleDateString();
        expectedBirthSpan.textContent = expectedBirth.toLocaleDateString();
    }

    // // Modal controls
    // closeModal.addEventListener('click', function() {
    //     modal.style.display = 'none';
    // });

    // window.addEventListener('click', function(event) {
    //     if (event.target === modal) {
    //         modal.style.display = 'none';
    //     }
    // });
    // Update the modal to show breed prediction
function updateBreedPrediction(eweBreed, ramBreed) {
    const predictionRules = {
        'LOCAL-LOCAL': { breed: 'LOCAL', level: '100%' },
        'PA-LOCAL': { breed: 'AC', level: '50%' },
        'LOCAL-PA': { breed: 'AC', level: '50%' },
        'PD-LOCAL': { breed: 'DC', level: '50%' },
        'LOCAL-PD': { breed: 'DC', level: '50%' },
        'AC-PA': { breed: 'AC', level: 'Average of parents' },
        'PA-AC': { breed: 'AC', level: 'Average of parents' },
        'DC-PD': { breed: 'DC', level: 'Average of parents' },
        'PD-DC': { breed: 'DC', level: 'Average of parents' },
        'PA-PA': { breed: 'PA', level: '100%' },
        'PD-PD': { breed: 'PD', level: '100%' }
    };
    
    const key = `${eweBreed}-${ramBreed}`;
    const prediction = predictionRules[key];
    
    const predictionElement = document.getElementById('breedPrediction');
    if (prediction) {
        predictionElement.innerHTML = `
            <div class="alert alert-success">
                <strong>Predicted Lamb Breed:</strong> ${prediction.breed}<br>
                <strong>Breed Level:</strong> ${prediction.level}
            </div>
        `;
    } else {
        predictionElement.innerHTML = `
            <div class="alert alert-warning">
                <strong>Lamb Breed:</strong> Manual assignment required<br>
                <small>This breed combination is not in the prediction table</small>
            </div>
        `;
    }
}

    // Form submission
    // breedingForm.addEventListener('submit', function(e) {
    //     e.preventDefault();
        
    //     const formData = {
    //         ewe_id: selectedEweId,
    //         ram_id: selectedRamId,
    //         start_date: startDateInput.value
    //     };

    //     fetch('/breeding/create-cycle/', {
    //         method: 'POST',
    //         headers: {
    //             'Content-Type': 'application/json',
    //             'X-CSRFToken': getCookie('csrftoken')
    //         },
    //         body: JSON.stringify(formData)
    //     })
    //     .then(response => response.json())
    //     .then(data => {
    //         if (data.success) {
    //             showMessage(data.message, 'success');
    //             modal.style.display = 'none';
    //             // Refresh the page after 2 seconds to show updated data
    //             setTimeout(() => {
    //                 window.location.reload();
    //             }, 2000);
    //         } else {
    //             showMessage(data.message, 'error');
    //         }
    //     })
    //     .catch(error => {
    //         showMessage('An error occurred: ' + error, 'error');
    //     });
    // });
    // Form submission
breedingForm.addEventListener('submit', function(e) {
    e.preventDefault();
    
    const startDateValue = startDateInput.value;
    
    // Basic date validation
    if (!startDateValue) {
        showToast('Please select a start date', 'error');
        return;
    }
    
    // Check if date is in the past
    const selectedDate = new Date(startDateValue);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    if (selectedDate < today) {
        showToast('Start date cannot be in the past', 'error');
        return;
    }
    
    const formData = {
        ewe_id: selectedEweId,
        ram_id: selectedRamId,
        start_date: startDateValue
    };

    fetch('create-cycle/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            modal.style.display = 'none';
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            showToast(data.message, 'error');
        }
    })
    .catch(error => {
        showToast('An error occurred: ' + error, 'error');
    });
});

    // Utility functions
    function showMessage(text, type) {
        const messagesContainer = document.getElementById('messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.textContent = text;
        
        messagesContainer.appendChild(messageDiv);
        
        setTimeout(() => {
            messageDiv.remove();
        }, 5000);
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Initial calculations
    calculateDates();
});