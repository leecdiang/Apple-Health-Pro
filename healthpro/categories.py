"""Explicit, exclusive HealthKit identifier routing. Unknowns are preserved."""

CATEGORIES = {
    "1_Heart_Cardio": "心血管",
    "2_Body_Metrics": "身体指标",
    "3_Daily_Activity": "日常活动",
    "4_Sleep_Recovery": "睡眠与恢复",
    "5_Mobility_Gait": "步态与行动力",
    "6_Reproductive": "生殖健康",
    "7_Vitals_Respiratory": "生命体征",
    "8_Running_Dynamics": "跑步动态",
    "9_Cycling_Stats": "骑行表现",
    "10_Swimming_Water": "游泳与水域",
    "11_Workouts_Training": "体能训练",
    "12_Environment_Senses": "环境与感官",
    "13_Nutrition_Hydration": "营养与饮水",
    "14_Mindfulness_Mental": "心理状态与正念",
    "15_Symptoms_Illness": "症状",
    "16_Other_Unmapped": "其他 / 未映射",
}

_QUANTITY_GROUPS = {
    "1_Heart_Cardio": "HeartRate RestingHeartRate HeartRateVariabilitySDNN WalkingHeartRateAverage HeartRateRecoveryOneMinute VO2Max AtrialFibrillationBurden PeripheralPerfusionIndex",
    "2_Body_Metrics": "BodyMass BodyMassIndex Height BodyFatPercentage LeanBodyMass BodyWaterMass WaistCircumference",
    "3_Daily_Activity": "StepCount ActiveEnergyBurned BasalEnergyBurned DistanceWalkingRunning FlightsClimbed AppleExerciseTime AppleMoveTime AppleStandTime PhysicalEffort",
    "4_Sleep_Recovery": "AppleSleepingWristTemperature",
    "5_Mobility_Gait": "WalkingSpeed WalkingStepLength WalkingAsymmetryPercentage WalkingDoubleSupportPercentage AppleWalkingSteadiness SixMinuteWalkTestDistance StairAscentSpeed StairDescentSpeed",
    "7_Vitals_Respiratory": "OxygenSaturation RespiratoryRate BodyTemperature BasalBodyTemperature BloodPressureSystolic BloodPressureDiastolic BloodGlucose ForcedVitalCapacity ForcedExpiratoryVolume1 PeakExpiratoryFlowRate InhalerUsage InsulinDelivery",
    "8_Running_Dynamics": "RunningPower RunningVerticalOscillation RunningGroundContactTime RunningStrideLength RunningSpeed",
    "9_Cycling_Stats": "CyclingPower CyclingCadence CyclingSpeed CyclingFunctionalThresholdPower DistanceCycling",
    "10_Swimming_Water": "DistanceSwimming SwimmingStrokeCount UnderwaterDepth WaterTemperature UnderwaterTime",
    "12_Environment_Senses": "TimeInDaylight EnvironmentalAudioExposure HeadphoneAudioExposure EnvironmentalSoundReduction UVExposure",
    "13_Nutrition_Hydration": "DietaryEnergyConsumed DietaryCarbohydrates DietaryProtein DietaryFatTotal DietaryFatSaturated DietaryFatMonounsaturated DietaryFatPolyunsaturated DietaryCholesterol DietarySodium DietaryFiber DietarySugar DietaryWater DietaryCaffeine DietaryCalcium DietaryIron DietaryPotassium DietaryVitaminA DietaryVitaminB6 DietaryVitaminB12 DietaryVitaminC DietaryVitaminD DietaryVitaminE DietaryVitaminK DietaryThiamin DietaryRiboflavin DietaryNiacin DietaryFolate DietaryBiotin DietaryPantothenicAcid DietaryPhosphorus DietaryIodine DietaryMagnesium DietaryZinc DietarySelenium DietaryCopper DietaryManganese DietaryChromium DietaryMolybdenum DietaryChloride",
}
_CATEGORY_GROUPS = {
    "1_Heart_Cardio": "HighHeartRateEvent LowHeartRateEvent IrregularHeartRhythmEvent AtrialFibrillationBulletin",
    "3_Daily_Activity": "AppleStandHour",
    "4_Sleep_Recovery": "SleepAnalysis SleepApneaEvent",
    "5_Mobility_Gait": "AppleWalkingSteadinessEvent",
    "6_Reproductive": "MenstrualFlow IntermenstrualBleeding CervicalMucusQuality OvulationTestResult SexualActivity PregnancyTestResult ProgesteroneTestResult Lactation Contraceptive Pregnancy PersistentIntermenstrualBleeding ProlongedMenstrualPeriods IrregularMenstrualCycles InfrequentMenstrualCycles",
    "12_Environment_Senses": "EnvironmentalAudioExposureEvent HeadphoneAudioExposureEvent",
    "14_Mindfulness_Mental": "MindfulSession StateOfMind",
    "15_Symptoms_Illness": "AbdominalCramps Bloating Constipation Diarrhea Heartburn Nausea Vomiting AppetiteChanges Chills Dizziness Fainting Fatigue Fever GeneralizedBodyAche HotFlashes ChestTightnessOrPain Coughing RapidPoundingOrFlutteringHeartbeat ShortnessOfBreath SkippedHeartbeat Wheezing LowerBackPain Headache MemoryLapse MoodChanges LossOfSmell LossOfTaste RunnyNose SoreThroat SinusCongestion BreastPain PelvicPain VaginalDryness Acne DrySkin HairLoss NightSweats SleepChanges BladderIncontinence",
}

TYPE_CATEGORY = {}
for prefix, groups in (("HKQuantityTypeIdentifier", _QUANTITY_GROUPS),
                       ("HKCategoryTypeIdentifier", _CATEGORY_GROUPS)):
    for category, names in groups.items():
        for name in names.split():
            identifier = prefix + name
            if identifier in TYPE_CATEGORY:
                raise ValueError("Duplicate category mapping: " + identifier)
            TYPE_CATEGORY[identifier] = category


def category_for(kind, identifier):
    if kind == "Workout":
        return "11_Workouts_Training"
    if kind == "StateOfMind":
        return "14_Mindfulness_Mental"
    return TYPE_CATEGORY.get(identifier, "16_Other_Unmapped")
