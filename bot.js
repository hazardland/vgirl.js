const axios = require("axios");
const readline = require("readline");
const fs = require("fs");
const chalk = require("chalk"); // Import chalk

// Load system prompt from text file
const loadPrompt = () => {
  try {
    const data = fs.readFileSync("./prompt.txt", "utf-8"); // Read the text file
    return data.trim(); // Trim any extra whitespace
  } catch (error) {
    console.error(chalk.red("Error loading system prompt:"), error.message);
    process.exit(1);
  }
};

const systemPrompt = loadPrompt(); // Load the system prompt

// Message history
const messageHistory = [
  { role: "system", content: systemPrompt } // Include system prompt at the start
];

// Trim message history to stay within token limits
function trimMessageHistory() {
  const maxMessages = 30; // Adjust based on token limit
  while (messageHistory.length > maxMessages) {
    messageHistory.splice(1, 1); // Keep the system prompt, remove oldest messages
  }
  // console.log(chalk.yellow(`Memory message count ${messageHistory.length}`))
}

// Re-inject system prompt at the end of the history
// function refreshSystemPrompt() {
//   messageHistory.push({ role: "system", content: systemPrompt });
//   console.log(chalk.red('System prompt reinjected'))
// }


// Function to send chat messages to the /api/chat endpoint
async function getAssistantResponse(userMessage) {

  // Only using even this works if we keep msg history to 15
  // And leave system message as first message
  trimMessageHistory();

  // Periodically re-inject system prompt or trim history
  // if (messageHistory.length % 10 === 0) {
  //   refreshSystemPrompt();
  // }

  // Add the user's message to the message history
  messageHistory.push({ role: "user", content: userMessage });

  try {
    const response = await axios.post("http://127.0.0.1:11434/api/chat", {
      model: "artifish/llama3.2-uncensored",
      messages: messageHistory,
      stream: false
    });

    const assistantMessage = response.data?.message?.content?.trim();
    if (assistantMessage) {
      messageHistory.push({ role: "assistant", content: assistantMessage });
    }

    return assistantMessage;
  } catch (error) {
    if (error?.response?.data?.error) {
      console.error(chalk.red("Error:"), error?.response?.data?.error);
    } else {
      console.error(chalk.red("Unexpected Error:"), error);
    }
    return "Sorry, something went wrong.";
  }
}

async function chatWithAssistant() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log(chalk.cyanBright("Say hi to your virtual assistant! Type 'exit' to quit.\n"));

  const askQuestion = (question) => {
    return new Promise((resolve) => rl.question(question, resolve));
  };

  const showSpinner = () => {
    const spinnerFrames = ["|", "/", "-", "\\"];
    let frameIndex = 0;
    const spinnerInterval = setInterval(() => {
      process.stdout.write(chalk.cyan(`\r${spinnerFrames[frameIndex++ % spinnerFrames.length]} `));
    }, 100);

    return () => {
      clearInterval(spinnerInterval);
      process.stdout.write("\r"); // Clear the spinner
    };
  };

  while (true) {
    const userMessage = await askQuestion(chalk.green(`You(${messageHistory.length}): `));
    if (userMessage.toLowerCase() === "exit") {
      console.log(chalk.yellow("Goodbye!"));
      rl.close();
      break;
    }

    const stopSpinner = showSpinner(); // Start the spinner

    try {
      const assistantResponse = await getAssistantResponse(userMessage); // Simulating the request
      stopSpinner(); // Stop the spinner
      if (assistantResponse) {
        console.log(chalk.blueBright(`>>>>(${messageHistory.length}): ${assistantResponse}`));
      }
    } catch (error) {
      stopSpinner(); // Ensure spinner stops even on error
      console.log(chalk.red("Error getting response from assistant."));
    }
  }
}
// // CLI Interface
// async function chatWithAssistant() {
//   const rl = readline.createInterface({
//     input: process.stdin,
//     output: process.stdout,
//   });

//   console.log(chalk.cyanBright("Say hi to your virtual assistant! Type 'exit' to quit.\n"));

//   const askQuestion = (question) => {
//     return new Promise((resolve) => rl.question(question, resolve));
//   };

//   while (true) {
//     const userMessage = await askQuestion(chalk.green("You: "));
//     if (userMessage.toLowerCase() === "exit") {
//       console.log(chalk.yellow("Goodbye!"));
//       rl.close();
//       break;
//     }

//     const assistantResponse = await getAssistantResponse(userMessage);
//     if (assistantResponse) {
//       console.log(chalk.blueBright(`>>>>: ${assistantResponse}`));
//     }
//   }
// }

chatWithAssistant();
