#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Tickable.h"
#include "WitnessBridgeSubsystem.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams(
    FWitnessNamedAction,
    FString, Target,
    FString, Key,
    int32, X,
    int32, Y);

UCLASS()
class WITNESSBRIDGE_API UWitnessBridgeSubsystem : public UGameInstanceSubsystem, public FTickableGameObject
{
    GENERATED_BODY()

public:
    UPROPERTY(BlueprintAssignable, Category = "Witness QA")
    FWitnessNamedAction OnNamedAction;

    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override { RETURN_QUICK_DECLARE_CYCLE_STAT(UWitnessBridgeSubsystem, STATGROUP_Tickables); }
    virtual bool IsTickable() const override { return bEnabled; }

private:
    bool bEnabled = false;
    FString BridgeDirectory;
    FString CommandPath;
    FString AckPath;
    FDateTime LastWriteTime = FDateTime::MinValue();
    double NextPollSeconds = 0.0;

    void WriteAck(const FString& Id, bool bOk, const FString& Error) const;
};
