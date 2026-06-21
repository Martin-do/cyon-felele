// static/js/autocomplete.js
// CYON Harvest - Smart Autocomplete

document.addEventListener('DOMContentLoaded', () => {
    const nameInput = document.getElementById('name');
    if (!nameInput) return;

    let resultsDiv = document.getElementById('autocomplete-results');
    if (!resultsDiv) {
        resultsDiv = document.createElement('div');
        resultsDiv.id = 'autocomplete-results';
        resultsDiv.style.cssText = 'display: none; position: absolute; top: 100%; left: 0; right: 0; background: var(--card-bg, #1e293b); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; z-index: 10; max-height: 200px; overflow-y: auto; backdrop-filter: blur(12px); box-shadow: 0 10px 15px rgba(0,0,0,0.3);';
        
        // Ensure parent has position relative
        nameInput.parentNode.style.position = 'relative';
        nameInput.parentNode.insertBefore(resultsDiv, nameInput.nextSibling);
    }

    let searchTimeout = null;

    nameInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        const query = nameInput.value.trim();

        if (query.length < 2) {
            resultsDiv.style.display = 'none';
            return;
        }

        searchTimeout = setTimeout(async () => {
            try {
                const response = await fetch(`/api/names/search/?q=${encodeURIComponent(query)}`);
                const data = await response.json();
                
                if (data.length > 0) {
                    resultsDiv.innerHTML = data.map(name => `
                        <div class="suggestion-item" data-name="${name.replace(/"/g, '&quot;')}" style="padding: 10px 15px; cursor: pointer; border-bottom: 1px solid rgba(255,255,255,0.05); transition: background 0.2s;">
                            ${name}
                        </div>
                    `).join('');
                    resultsDiv.style.display = 'block';

                    // Attach click handlers
                    const items = resultsDiv.querySelectorAll('.suggestion-item');
                    items.forEach(item => {
                        item.addEventListener('click', () => {
                            nameInput.value = item.getAttribute('data-name');
                            resultsDiv.style.display = 'none';
                            
                            // Move focus to amount
                            const amountInput = document.getElementById('display_amount');
                            if (amountInput) amountInput.focus();
                        });
                        item.addEventListener('mouseenter', () => item.style.backgroundColor = 'rgba(255,255,255,0.1)');
                        item.addEventListener('mouseleave', () => item.style.backgroundColor = 'transparent');
                    });
                } else {
                    resultsDiv.style.display = 'none';
                }
            } catch (e) {
                console.error("Search failed", e);
            }
        }, 300); // 300ms debounce
    });

    // Close on Escape
    nameInput.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            resultsDiv.style.display = 'none';
        }
    });

    // Close if clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.form-group')) {
            resultsDiv.style.display = 'none';
        }
    });
});
