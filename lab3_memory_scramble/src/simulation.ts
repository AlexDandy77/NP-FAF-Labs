import { Board } from './board.js';
import { look, flip } from './commands.js';

/**
 * Simulation script for a game of Memory Scramble.
 * Simulates multiple players making random moves with random timeouts.
 * 
 * @throws Error if an error occurs reading or parsing the board
 */
async function simulationMain(): Promise<void> {
    const filename = 'boards/perfect.txt';
    const board: Board = await Board.parseFromFile(filename);
    
    // Default dimensions
    let height = 4;
    let width = 4;
    
    try {
        // Get initial board state to determine dimensions
        const initialState = await look(board, 'init');
        const firstLine = initialState.split('\n')[0] ?? '';
        const match = firstLine.match(/^(\d+)x(\d+)$/);
        if (typeof match?.[1] === 'string' && typeof match?.[2] === 'string') {
            const h = parseInt(match[1], 10);
            const w = parseInt(match[2], 10);
            if (!isNaN(h) && !isNaN(w) && h > 0 && w > 0) {
                height = h;
                width = w;
            }
        }
    } catch (err) {
        console.warn('Could not determine board dimensions, using defaults:', err);
    }
    
    const players = 2;
    const tries = 20;
    const maxDelayMilliseconds = 100;

    // start up one or more players as concurrent asynchronous function calls
    const playerPromises: Array<Promise<void>> = [];
    for (let ii = 0; ii < players; ++ii) {
        playerPromises.push(player(ii, width, height));
    }
    // wait for all the players to finish (unless one throws an exception)
    await Promise.all(playerPromises);

    /** 
     * @param playerNumber player to simulate
     * @param boardWidth width of the game board
     * @param boardHeight height of the game board
     */
    async function player(playerNumber: number, boardWidth: number, boardHeight: number): Promise<void> {
        const playerId = `player${playerNumber}`;
        console.log(`\n--- Starting player ${playerId} ---`);

        // Initial board state
        console.log('Initial board state:');
        console.log(await look(board, playerId));

        for (let jj = 0; jj < tries; ++jj) {
            try {
                // Random delay before first flip
                await timeout(Math.random() * maxDelayMilliseconds);

                // Gets available card positions from current board state
                /**
                 * Get available card positions from the current board state.
                 * Returns positions where the line is a string and indicates a face-down card.
                 * @returns Array of objects with row and col properties for available positions
                 */
                async function getAvailablePositions(): Promise<Array<{row: number; col: number}>> {
                    const currentState = await look(board, playerId);
                    const lines = currentState.split('\n');
                    const positions: Array<{row: number; col: number}> = [];

                    for (let row = 0; row < boardHeight; row++) {
                        for (let col = 0; col < boardWidth; col++) {
                            const index = 1 + row * boardWidth + col; // +1 because first line is dimensions
                            const line = lines[index];
                            if (typeof line === 'string' && !line.startsWith('none') && line.startsWith('down')) {
                                positions.push({row, col});
                            }
                        }
                    }
                    return positions;
                }

                // Get available positions for first flip
                const initialPositions = await getAvailablePositions();
                if (initialPositions.length < 2) {
                    console.log(`${playerId}: Not enough cards left to play!`);
                    break; // Exit the game loop
                }

                // Randomly select first card position
                const firstCardIndex = randomInt(initialPositions.length);
                const firstCardPos = initialPositions[firstCardIndex];
                if (!firstCardPos) {
                    console.error(`${playerId}: Failed to select a valid card position`);
                    continue;
                }
                
                console.log(`\n${playerId}: Attempting to flip first card at (${firstCardPos.row}, ${firstCardPos.col})`);
                const firstFlipState = await flip(board, playerId, firstCardPos.row, firstCardPos.col);
                console.log(`${playerId}: First flip result:\n${firstFlipState}`);

                // Random delay before second flip
                await timeout(Math.random() * maxDelayMilliseconds);
                
                // Get fresh state for second flip (some cards might have been removed)
                const remainingPositions = (await getAvailablePositions())
                    .filter(pos => pos.row !== firstCardPos.row || pos.col !== firstCardPos.col);
                
                if (remainingPositions.length === 0) {
                    console.log(`${playerId}: No more valid cards to flip!`);
                    continue;
                }

                const secondCardPos = remainingPositions[randomInt(remainingPositions.length)];
                if (!secondCardPos) {
                    console.error(`${playerId}: Failed to select a valid second card position`);
                    continue;
                }
                const row2 = secondCardPos.row;
                const col2 = secondCardPos.col;
                
                console.log(`\n${playerId}: Attempting to flip second card at (${row2}, ${col2})`);
                const secondFlipState = await flip(board, playerId, row2, col2);
                console.log(`${playerId}: Second flip result:\n${secondFlipState}`);

                // Look at the board after both flips
                const finalState = await look(board, playerId);
                console.log(`${playerId}: Board after both flips:\n${finalState}`);
                console.log('-------------------');

                // Add a delay after each turn to let the board update
                await timeout(maxDelayMilliseconds);

            } catch (err) {
                console.error(`${playerId}: attempt to flip a card failed:`, err);
            }
        }
        
        // Final board state
        console.log(`Final board state for ${playerId}:`);
        console.log(await look(board, playerId));
    }
}

/**
 * Random positive integer generator
 * 
 * @param max a positive integer which is the upper bound of the generated number
 * @returns a random integer >= 0 and < max
 */
function randomInt(max: number): number {
    return Math.floor(Math.random() * max);
}


/**
 * @param milliseconds duration to wait
 * @returns a promise that fulfills no less than `milliseconds` after timeout() was called
 */
async function timeout(milliseconds: number): Promise<void> {
    const { promise, resolve } = Promise.withResolvers<void>();
    setTimeout(resolve, milliseconds);
    return promise;
}

void simulationMain();
