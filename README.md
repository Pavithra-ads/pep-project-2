# AI-Based Public Speaking Evaluation System

An AI-powered public speaking evaluation system that analyzes recorded speech and provides structured feedback on filler words, repeated words and phrases, long pauses, and speaking duration.

## Project Overview

Public speaking is commonly evaluated manually by mentors or peers, which can make the evaluation process time-consuming and inconsistent. Important speech patterns such as filler words, repetitions, and long pauses may also be overlooked.

This project automates the evaluation of recorded speeches using **Natural Language Processing (NLP)**, **Machine Learning**, and **rule-based speech analysis** techniques.

The system allows a user to upload a recorded speech video. The video is processed to extract the speech, generate a timestamped transcript, analyze speech patterns, and classify speech segments using a fine-tuned BERT model.

The results from the AI classification and speech analysis are combined to generate a structured speech evaluation report.

## Objectives

- Automate public speaking evaluation
- Identify filler words and phrases
- Detect repeated words and phrases
- Detect long pauses
- Calculate speaking duration
- Classify speech segments based on speech disfluencies
- Generate structured and consistent feedback
- Help speakers identify areas for improvement

## Dataset

A custom labeled dataset was prepared from speech transcript data for training the BERT classification model.

The dataset contains **7,953 speech sentences** classified into four categories:

| Label | Description |
|---|---|
| NORMAL | Sentence without significant filler or repetition |
| FILLER | Sentence containing filler words or phrases |
| REPETITION | Sentence containing repeated speech elements |
| BOTH | Sentence containing both filler and repetition |

### Dataset Distribution

| Class | Number of Samples |
|---|---:|
| NORMAL | 5,353 |
| FILLER | 2,099 |
| REPETITION | 251 |
| BOTH | 250 |
| **Total** | **7,953** |

### Dataset Files

- **Dataset link1:https://youtu.be/MdeQMVBuGgY?si=U2SEj5Pq7TPHQ62m** 
- **Dataset link2: https://youtu.be/Pkk7pGFfxxQ?si=0kg66t0gVi6vcnTY** 
- **Dataset link3:https://youtu.be/90lLQVZe2Nc?si=njk0R8-mJdir-hAj** 

### Dataset Preparation

```text
Speech Transcript Data
        ↓
Extract Sentence Text
        ↓
Clean Dataset
        ↓
Apply Filler & Repetition Labels
        ↓
Label Validation / Correction
        ↓
Final Labeled Dataset
        ↓
BERT Fine-Tuning
