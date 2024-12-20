import requests
from jira import JIRA
import re
from unidiff import PatchSet
import openai
from colorama import Back, Fore, Style, init
import argparse
import os
from dotenv import load_dotenv

load_dotenv()

init(autoreset=True)

# Keep track of ticket links
explained_tickets = []

openai.api_key = os.getenv('OPEN_AI_KEY')

BITBUCKET_BASE_URL = os.getenv('BITBUCKET_BASE_URL')
BITBUCKET_USERNAME = os.getenv('BITBUCKET_USERNAME')
BITBUCKET_APP_PASSWORD = os.getenv('BITBUCKET_APP_PASSWORD')
REPO_SLUG = os.getenv('REPO_SLUG')
WORKSPACE = os.getenv('WORKSPACE')

JIRA_URL = os.getenv('JIRA_URL')
JIRA_USERNAME = os.getenv('JIRA_USERNAME')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')

jira = JIRA(server=JIRA_URL, basic_auth=(JIRA_USERNAME, JIRA_API_TOKEN))

# Function to fetch merged pull requests from Bitbucket
def get_merged_pull_requests():
    url = f'{BITBUCKET_BASE_URL}/repositories/{WORKSPACE}/{REPO_SLUG}/pullrequests?state=ALL'
    response = requests.get(url, auth=(BITBUCKET_USERNAME, BITBUCKET_APP_PASSWORD))
    if response.status_code == 200:
        return response.json()['values']
    else:
        print(f"Error fetching PRs: {response.status_code}")
        return None

# Function to extract Jira ticket number from PR title
def extract_ticket_number(pr_title):
    match = re.search(r'(TT-\d+)', pr_title)  # Modify the regex pattern based on your ticket format
    if match:
        return match.group(1)
    return None

# Function to fetch Jira ticket details
def get_jira_ticket(ticket_number):
    try:
        issue = jira.issue(ticket_number)
        return issue
    except Exception as e:
        print(f"Error fetching Jira ticket: {e}")
        return None

def get_pr_diff(pr_id):
    url = f'{BITBUCKET_BASE_URL}/repositories/{WORKSPACE}/{REPO_SLUG}/pullrequests/{pr_id}/diff'
    response = requests.get(url, auth=(BITBUCKET_USERNAME, BITBUCKET_APP_PASSWORD))
    if response.status_code == 200:
        return response.text
    else:
        print(f"Error fetching diff for PR {pr_id}: {response.status_code}")
        return None

def analyze_diff(diff_text):
    patch_set = PatchSet(diff_text)
    for patched_file in patch_set:
        print(f"\nFile: {patched_file.path}")
        for hunk in patched_file:
            print(f"Hunk with {hunk.added} lines added and {hunk.removed} lines removed:")
            for line in hunk:
                if line.is_added:
                    print(f"Added: {line.value.strip()}")
                elif line.is_removed:
                    print(f"Removed: {line.value.strip()}")

def generate_explanation(ticket, diff_text):
    prompt = f"""
   You are a senior Magento developer mentoring a junior developer. Please explain these changes in detail, focusing on teaching concepts, best practices, and real-world applications. Format your response into six sections:

Code Changes Explained:

Provide a clear and step-by-step explanation of the code changes, including the context of the modifications and how they work. Include code snippets of the updated code, highlight key parts, and explain what they do.
If applicable, describe how these changes interact with core Magento features, custom modules, or third-party extensions (e.g., Webkul Marketplace or Dynamics 365 integration).
Why These Changes Might Have Been Necessary:

Explain the reasoning behind these changes. Describe the specific issue or requirement that prompted the changes and how they address the problem.
Use statements like "this was done because" or "this solves the problem by" to clearly convey the thought process behind the decisions.
Key Magento Concepts and Practices:

Highlight the Magento 2 concepts, patterns, and features relevant to these changes (e.g., dependency injection, observers, plugins, UI components).
Relate these concepts to the changes made, providing insights into how they can be applied in other contexts.
Possible Improvements:

Suggest potential ways to enhance the code, focusing on Magento 2 best practices, performance optimization, and maintainability.
Include concrete examples of how the current code could be refactored or improved, with before-and-after code snippets. Emphasize principles like single responsibility, reusability, and modularity.
Relevant Documentation, Links, and References:

Provide links to relevant Magento 2 documentation, community articles, or official guides that explain related concepts.
Include suggestions for further reading to deepen the developer's understanding of Magento 2.
Conclusion and Learning Points:

Summarize the key learning points from these changes and how they contribute to the overall functionality of the project.
Include practical takeaways or tips for the junior developer to apply in future Magento 2 development tasks.
Your feedback should be clear, structured, and tailored for a junior developer who is eager to learn and improve. Focus on breaking down complex concepts into digestible pieces, providing actionable advice, and encouraging thoughtful decision-making in Magento 2 development.

    Code Diff:
    {diff_text}
    """

    # Non-streaming request using OpenAI client
    completion = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert in Magento 2 development teaching a jr developer relatively new to magento.  You work on a customized instance of magento2 that utilizes the webkul marketplace extension and integrates with dynamics 365 finance and operations, rabbit mq, and a headless react application for creating garment logo mock ups"},
            {"role": "user", "content": prompt}
        ]
    )
    
    return completion.choices[0].message.content.strip()


def format_text(text):
    # Style ### lines and **bold** text with specific colors
    text = text.replace('###', "")

    # Use cyan for headers
    text = text.replace('Code Changes Explained:', f"{Back.CYAN} Code Changes Explained:{Style.RESET_ALL}\n")
    text = text.replace('Why These Changes Might Have Been Necessary:', f"{Back.CYAN} Why These Changes Might Have Been Necessary:{Style.RESET_ALL}\n")
    text = text.replace('Conclusion:', f"{Back.CYAN} Conclusion:{Style.RESET_ALL}\n")
    text = text.replace('Relevant Documentation, Links, and References:', f"{Back.CYAN} Relevant Documentation, Links, and References:{Style.RESET_ALL}\n")
    text = text.replace('Possible Improvements:', f"{Back.CYAN} Possible Improvements:{Style.RESET_ALL}\n")


    
    # Apply cyan color for text between ** (bold text)
    formatted_text = ""
    in_bold = False
    in_code_block = False
    
    i = 0
    while i < len(text):
        # Start and end bold text
        if text[i:i+2] == "**":
            in_bold = not in_bold  # Toggle bold flag
            if in_bold:
                formatted_text += f"{Fore.CYAN}"  # Start cyan + bright
            else:
                formatted_text += f"{Style.RESET_ALL}"  # Reset formatting
            i += 2
        # Colorize text within backticks (`text`)
        elif text[i] == "`":
            formatted_text += f"{Fore.GREEN}{text[i]}"  # Start GREEN for backticks
            i += 1
            while i < len(text) and text[i] != "`":
                formatted_text += f"{Fore.GREEN}{text[i]}"
                i += 1
            formatted_text += f"{Fore.GREEN}`{Style.RESET_ALL}"  # End GREEN
            i += 1
        # Code block in green
        elif text[i:i+3] == "```":
            in_code_block = not in_code_block
            if in_code_block:
                formatted_text += f"\n{Fore.GREEN}"  # Start green for code block
            else:
                formatted_text += f"{Style.RESET_ALL}\n"  # End code block
            i += 3
        # Handle everything else
        else:
            formatted_text += text[i]
            i += 1

    


    return formatted_text

def generate_explanation_for_pr(pr, jira_ticket, diff_text, count, pr_url):
    explanation = generate_explanation(f"{jira_ticket.key} - {jira_ticket.fields.summary}", diff_text)

    ticket_number = extract_ticket_number(pr['title'])  
    jira_url = f"https://gearupsports.atlassian.net/browse/{ticket_number}"    
    
    # Print the formatted output, including the PR URL
    print(f"{Back.GREEN}Jira Ticket: {jira_ticket.key} - {jira_ticket.fields.summary}{Style.RESET_ALL}\n")
    print(f"{Back.GREEN}Ticket Link: {jira_url} | PR: {pr['title']} | {pr_url}")
    
    
    # Format Explanation
    print(format_text(explanation))
    
    # Print line separator
    print(f"{Style.RESET_ALL}\n{'-' * 80}\n")
    
    return count + 1



def main():
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description='PR Explainer Script')
    parser.add_argument('-t', '--ticket', type=str, help='Jira ticket number to process (e.g., TT-3964)')
    parser.add_argument('-e', '--extract-diff', action='store_true', help='Extract and print the diff without analyzing it')
    args = parser.parse_args()

    # Fetch merged PRs
    merged_prs = get_merged_pull_requests()

    if merged_prs:
        count = 0
        for pr in merged_prs:
            ticket_number = extract_ticket_number(pr['title'])
            if ticket_number:
                # If a specific ticket is provided, only process that one
                if args.ticket and args.ticket != ticket_number:
                    continue

                jira_ticket = get_jira_ticket(ticket_number)
                if jira_ticket:
                    pr_diff = get_pr_diff(pr['id'])
                    if pr_diff:
                        pr_url = pr['links']['self']['href']  # Extract pull request link
                        
                        # Extract the diff without analyzing if the flag is set
                        if args.extract_diff:
                            print(f"{Fore.GREEN}PR: {pr['title']} | {pr_url}")
                            print(f"{Fore.YELLOW}Jira Ticket: {jira_ticket.key} - {jira_ticket.fields.summary}")
                            print(f"{Fore.CYAN}### Code Diff:\n")
                            print(pr_diff)
                            print(f"{Style.RESET_ALL}\n{'-' * 80}\n")
                        else:
                            # Generate explanation for the PR if the flag is not set
                            count = generate_explanation_for_pr(pr, jira_ticket, pr_diff, count, pr_url)

        # List of all explained tickets with PR links (only when not extracting diff)
        if not args.extract_diff:
            print(f"{Fore.MAGENTA}### List of Explained Tickets:\n")
            for pr in merged_prs:
                ticket_number = extract_ticket_number(pr['title'])
                jira_url = f"https://gearupsports.atlassian.net/browse/{ticket_number}"
                pr_url = pr['links']['self']['href']  # Extract pull request link
                print(f"- [{ticket_number}]({jira_url}) | PR: [{pr['id']}]({pr_url})")

if __name__ == '__main__':
    main()

